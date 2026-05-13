"""
POST /callresults

Receives Vapi end-of-call-report (sent to the assistant-level server.url).
Saves the call recording, transcript, cost, and summary to Airtable.
"""

import hmac
import logging
import os

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

load_dotenv()
logger = logging.getLogger(__name__)

from tools.airtable_utils import upsert_call_recording
from tools.limiter import limiter

router = APIRouter()

_VAPI_SECRET = os.getenv("VAPI_WEBHOOK_SECRET", "")
if not _VAPI_SECRET:
    logger.critical(
        "VAPI_WEBHOOK_SECRET is not set — /callresults is unauthenticated. "
        "Add VAPI_WEBHOOK_SECRET to .env to secure this endpoint."
    )


@router.post("/callresults")
@limiter.limit("30/minute")
async def call_results(request: Request, authorization: str = Header(default="")):
    if _VAPI_SECRET:
        expected = f"Bearer {_VAPI_SECRET}"
        if not hmac.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(status_code=401, detail="Unauthorized")

    body = await request.json()
    message = body.get("message", {})

    if message.get("type") != "end-of-call-report":
        return JSONResponse({"status": "ignored"})

    call_obj   = message.get("call", {})
    call_id    = call_obj.get("id", "")
    cost       = message.get("cost")
    transcript = message.get("transcript", "")
    summary    = message.get("summary", "")
    started_at = message.get("startedAt", "")
    ended_at   = message.get("endedAt", "")

    artifact       = message.get("artifact", {})
    recording_url  = artifact.get("recordingUrl") or message.get("recordingUrl", "")

    customer       = call_obj.get("customer", {})
    customer_phone = customer.get("number", "")

    call_length = None
    if started_at and ended_at:
        try:
            from datetime import datetime, timezone
            fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
            s = datetime.strptime(started_at, fmt).replace(tzinfo=timezone.utc)
            e = datetime.strptime(ended_at,   fmt).replace(tzinfo=timezone.utc)
            call_length = (e - s).total_seconds()
        except Exception:
            pass

    try:
        upsert_call_recording(
            call_id=call_id,
            cost=cost,
            recording_url=recording_url,
            transcript=transcript,
            customer_number=customer_phone,
            started_at=started_at,
            ended_at=ended_at,
            call_length_secs=call_length,
            call_summary=summary,
        )
    except Exception as e:
        logger.exception("Airtable error saving call recording")
        return JSONResponse({"status": "error"})

    return JSONResponse({"status": "ok"})
