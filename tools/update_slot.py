"""
POST /updateslots

Reschedule an existing booking to a new time.

Looks up the most recently confirmed/updated booking by phone number from Airtable,
checks that the assigned technician and driver are free at the new time,
then patches both Google Calendar events using the stored calendar/event IDs.

Rolls back the technician event if the driver event update fails.

Vapi field names (after fixing the double-t typo in UpdateSlots2 schema):
  phone, Rescheduled_starttime, rescheduled_endtime
"""

import json as _json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from tools.airtable_utils import find_latest_booking, update_booking_times
from tools.calendar_utils import batch_freebusy, update_event, validate_time_window

router = APIRouter()


@router.post("/updateslots")
async def update_slot(request: Request):
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

    phone     = str(args.get("phone", "")).strip()
    new_start = str(args.get("Rescheduled_starttime", "")).strip()
    new_end   = str(args.get("rescheduled_endtime", "")).strip()

    if not phone or not new_start or not new_end:
        return _result(tool_call_id, "missing_required_fields: phone, Rescheduled_starttime, rescheduled_endtime required")

    # Validate the new time window before touching any calendar
    time_err = validate_time_window(new_start, new_end)
    if time_err:
        return _result(tool_call_id, f"invalid_time: {time_err}")

    # Find the most recent active booking for this phone number
    record = find_latest_booking(phone)
    if not record:
        return _result(tool_call_id, "booking_not_found")

    fields = record["fields"]
    tech_cal_id     = fields.get("TechnicianCalendarId", "")
    tech_event_id   = fields.get("TechnicianEventId", "")
    driver_cal_id   = fields.get("DriverCalendarId", "")
    driver_event_id = fields.get("DriverEventId", "")

    # Read original times for rollback
    original_start = fields.get("starttime", "")
    original_end   = fields.get("endtime", "")

    # Check that tech and driver are free at the new time
    # (FreeBusy will include the existing event if new window overlaps old one;
    #  that's acceptable — it prevents booking into a conflicting slot.)
    if tech_cal_id:
        try:
            busy_tech = batch_freebusy([tech_cal_id], new_start, new_end)
            if tech_cal_id in busy_tech:
                return _result(tool_call_id, "no_available_technician_at_new_time")
        except Exception:
            logger.exception("freebusy check failed for technician")
            return _result(tool_call_id, "calendar_error: freebusy_check_failed")

    if driver_cal_id:
        try:
            busy_driver = batch_freebusy([driver_cal_id], new_start, new_end)
            if driver_cal_id in busy_driver:
                return _result(tool_call_id, "no_available_driver_at_new_time")
        except Exception:
            logger.exception("freebusy check failed for driver")
            return _result(tool_call_id, "calendar_error: freebusy_check_failed")

    # Update technician calendar event
    if tech_cal_id and tech_event_id:
        try:
            update_event(tech_cal_id, tech_event_id, new_start, new_end)
        except Exception:
            logger.exception("could not update technician calendar event")
            return _result(tool_call_id, "calendar_error: could_not_update_technician_event")

    # Update driver calendar event — rollback tech event on failure
    if driver_cal_id and driver_event_id:
        try:
            update_event(driver_cal_id, driver_event_id, new_start, new_end)
        except Exception:
            logger.exception("could not update driver calendar event")
            if tech_cal_id and tech_event_id and original_start and original_end:
                try:
                    update_event(tech_cal_id, tech_event_id, original_start, original_end)
                except Exception:
                    pass
            return _result(tool_call_id, "calendar_error: could_not_update_driver_event")

    # Update Airtable record
    try:
        update_booking_times(record["id"], new_start, new_end)
    except Exception:
        logger.exception("airtable update failed")
        return _result(tool_call_id, "airtable_error: update_failed")

    return _result(tool_call_id, "Confirmed")


def _result(tool_call_id: str, result: str):
    return JSONResponse({"results": [{"toolCallId": tool_call_id, "result": result}]})
