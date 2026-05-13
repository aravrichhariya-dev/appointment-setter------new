"""
POST /getslots

Lightweight availability check. Tells Vapi/Ellie whether a technician is free
at the requested time so she can confirm with the caller before collecting
all booking details.

Does NOT assign a technician. BookSlots is the authoritative booking step.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tools.calendar_utils import batch_freebusy, validate_time_window
from tools.config import normalize_service, ranked_technicians
from tools.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/getslots")
@limiter.limit("60/minute")
async def get_slots(request: Request):
    body = await request.json()

    # Unpack Vapi tool-call envelope
    message = body.get("message", {})
    tool_calls = message.get("toolCallList", [])
    if not tool_calls:
        return JSONResponse({"error": "no toolCallList"}, status_code=400)

    call = tool_calls[0]
    tool_call_id = call["id"]

    import json as _json
    args = _json.loads(call["function"]["arguments"]) if isinstance(call["function"]["arguments"], str) else call["function"]["arguments"]

    service_text = args.get("service", "")
    starttime    = args.get("starttime", "")
    endtime      = args.get("endtime", "")

    if not service_text or not starttime or not endtime:
        return _result(tool_call_id, "missing_required_fields")

    time_err = validate_time_window(starttime, endtime)
    if time_err:
        return _result(tool_call_id, f"invalid_time: {time_err}")

    service_category = normalize_service(service_text)
    techs = ranked_technicians(service_category)

    try:
        busy_cal_ids = batch_freebusy([t["calendar_id"] for t in techs], starttime, endtime)
    except Exception as exc:
        logger.exception("batch_freebusy failed: %s", exc)
        return _result(tool_call_id, "calendar_error: freebusy_failed")

    for tech in techs:
        if tech["calendar_id"] not in busy_cal_ids:
            return _result(tool_call_id, "available")

    return _result(tool_call_id, "no_technician_available_for_that_time")


def _result(tool_call_id: str, result: str):
    return JSONResponse({"results": [{"toolCallId": tool_call_id, "result": result}]})
