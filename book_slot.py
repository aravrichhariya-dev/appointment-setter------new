"""
POST /bookslots

Atomic check-and-book. Does its own authoritative FreeBusy scan before booking,
so double-bookings are impossible regardless of what GetSlots returned.

Steps:
  1. Validate required fields
  2. Normalize service → internal category
  3. Find first available technician (by skill priority)
  4. Find first available driver
  5. Create technician Google Calendar event
  6. Create driver Google Calendar event
  7. Save booking to Airtable
  8. Return "confirmed"
"""

import json as _json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

from tools.airtable_utils import create_booking, upsert_customer
from tools.calendar_utils import batch_freebusy, create_event, delete_event, validate_time_window
from tools.config import DRIVERS, normalize_service, ranked_technicians
from tools.limiter import limiter

router = APIRouter()

REQUIRED_FIELDS = ("name", "phone", "address", "service", "starttime", "endtime")


@router.post("/bookslots")
@limiter.limit("30/minute")
async def book_slot(request: Request):
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

    # 1. Validate required fields
    missing = [f for f in REQUIRED_FIELDS if not str(args.get(f, "")).strip()]
    if missing:
        return _result(tool_call_id, f"missing_required_fields: {', '.join(missing)}")

    name      = str(args["name"]).strip()[:100]
    phone     = str(args["phone"]).strip()[:30]
    address   = str(args["address"]).strip()[:200]
    service   = str(args["service"]).strip()[:100]
    starttime = args["starttime"]
    endtime   = args["endtime"]
    issue     = str(args.get("issuedescription", "")).strip()[:500]
    notes     = str(args.get("notes", "")).strip()[:500]

    # 2. Validate time window
    time_err = validate_time_window(starttime, endtime)
    if time_err:
        return _result(tool_call_id, f"invalid_time: {time_err}")

    # 3. Normalize service
    service_category = normalize_service(service)

    # 4. Find available technician
    techs = ranked_technicians(service_category)
    try:
        busy_tech_cal_ids = batch_freebusy([t["calendar_id"] for t in techs], starttime, endtime)
    except Exception as e:
        logger.exception("freebusy check failed for technicians")
        return _result(tool_call_id, "calendar_error: freebusy_failed")
    chosen_tech = next((t for t in techs if t["calendar_id"] not in busy_tech_cal_ids), None)
    if not chosen_tech:
        return _result(tool_call_id, "no_available_technician")

    # 5. Find available driver
    try:
        busy_driver_cal_ids = batch_freebusy([d["calendar_id"] for d in DRIVERS], starttime, endtime)
    except Exception as e:
        logger.exception("freebusy check failed for drivers")
        return _result(tool_call_id, "calendar_error: freebusy_failed")
    chosen_driver = next((d for d in DRIVERS if d["calendar_id"] not in busy_driver_cal_ids), None)
    if not chosen_driver:
        return _result(tool_call_id, "no_available_driver")

    # 6. Create technician calendar event
    tech_summary = f"HVAC – {service} – {name}"
    tech_desc = (
        f"Service: {service}\n"
        f"Address: {address}\n"
        f"Issue: {issue}\n"
        f"Notes: {notes}\n"
        f"Phone: {phone}\n"
        f"Driver: {chosen_driver['name']}"
    )
    try:
        tech_event_id = create_event(
            chosen_tech["calendar_id"], tech_summary, tech_desc, starttime, endtime
        )
    except Exception as e:
        logger.exception("could not create technician calendar event")
        return _result(tool_call_id, "calendar_error: create_event_failed")

    # 7. Create driver calendar event
    driver_summary = f"Drive – {service} – {name}"
    driver_desc = (
        f"Drive for technician: {chosen_tech['name']}\n"
        f"Service: {service}\n"
        f"Address: {address}\n"
        f"Phone: {phone}"
    )
    try:
        driver_event_id = create_event(
            chosen_driver["calendar_id"], driver_summary, driver_desc, starttime, endtime
        )
    except Exception as e:
        # Rollback tech event
        try:
            delete_event(chosen_tech["calendar_id"], tech_event_id)
        except Exception:
            pass
        logger.exception("could not create driver calendar event")
        return _result(tool_call_id, "calendar_error: create_event_failed")

    # 8. Save to Airtable
    try:
        create_booking(
            name=name,
            phone=phone,
            address=address,
            service=service,
            starttime=starttime,
            endtime=endtime,
            issue_description=issue,
            notes=notes,
            technician_name=chosen_tech["name"],
            technician_calendar_id=chosen_tech["calendar_id"],
            technician_event_id=tech_event_id,
            driver_name=chosen_driver["name"],
            driver_calendar_id=chosen_driver["calendar_id"],
            driver_event_id=driver_event_id,
        )
    except Exception as e:
        # Rollback both calendar events
        try:
            delete_event(chosen_tech["calendar_id"], tech_event_id)
        except Exception:
            pass
        try:
            delete_event(chosen_driver["calendar_id"], driver_event_id)
        except Exception:
            pass
        logger.exception("airtable save failed")
        return _result(tool_call_id, "airtable_error: save_failed")

    # 9. Update customer profile (non-blocking — booking already confirmed)
    try:
        upsert_customer(phone=phone, name=name, address=address)
    except Exception:
        logger.exception("upsert_customer failed — customer record not saved for phone %s", phone)

    return _result(tool_call_id, "confirmed")


def _result(tool_call_id: str, result: str):
    return JSONResponse({"results": [{"toolCallId": tool_call_id, "result": result}]})
