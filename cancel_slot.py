"""
POST /cancelslots

Cancel an existing booking.

Fetches stored calendar/event IDs from Airtable, deletes both calendar events,
then marks the Airtable record as Canceled. Airtable is only updated AFTER
successful calendar deletions (404s are treated as success — already gone).
"""

import json as _json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from tools.airtable_utils import cancel_booking, find_latest_booking
from tools.calendar_utils import delete_event

router = APIRouter()


@router.post("/cancelslots")
async def cancel_slot(request: Request):
    body = await request.json()

    message = body.get("message", {})
    tool_calls = message.get("toolCallList", [])
    if not tool_calls:
        return JSONResponse({"error": "no toolCallList"}, status_code=400)

    call = tool_calls[0]
    tool_call_id = call["id"]
    args = call["function"]["arguments"]
    if isinstance(args, str):
        args = _json.loads(args)

    phone = str(args.get("phone", "")).strip()
    if not phone:
        return _result(tool_call_id, "missing_required_fields: phone required")

    record = find_latest_booking(phone)
    if not record:
        return _result(tool_call_id, "booking_not_found")

    fields = record["fields"]
    tech_cal_id     = fields.get("TechnicianCalendarId", "")
    tech_event_id   = fields.get("TechnicianEventId", "")
    driver_cal_id   = fields.get("DriverCalendarId", "")
    driver_event_id = fields.get("DriverEventId", "")

    # Delete technician event (404 = already gone, not an error)
    if tech_cal_id and tech_event_id:
        try:
            delete_event(tech_cal_id, tech_event_id)
        except Exception:
            logger.exception("could not delete technician calendar event")
            return _result(tool_call_id, "calendar_error: could_not_delete_technician_event")

    # Delete driver event
    if driver_cal_id and driver_event_id:
        try:
            delete_event(driver_cal_id, driver_event_id)
        except Exception:
            logger.exception("could not delete driver calendar event")
            return _result(tool_call_id, "calendar_error: could_not_delete_driver_event")

    # Only mark canceled after calendar operations succeed
    try:
        cancel_booking(record["id"])
    except Exception:
        logger.exception("airtable cancel failed")
        return _result(tool_call_id, "airtable_error: cancel_failed")

    return _result(tool_call_id, "Canceled")


def _result(tool_call_id: str, result: str):
    return JSONResponse({"results": [{"toolCallId": tool_call_id, "result": result}]})
