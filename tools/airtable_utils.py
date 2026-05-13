"""
Airtable helpers for the HVAC appointment system.

Tables (configured via environment variables):
  Appointments   — AIRTABLE_APPOINTMENTS_TABLE
  Call Recording — AIRTABLE_CALL_RECORDING_TABLE
  Customers      — AIRTABLE_CUSTOMERS_TABLE
"""

import os
import re
from datetime import date

from dotenv import load_dotenv
from pyairtable import Api

load_dotenv()

APPOINTMENTS_TABLE   = os.environ.get("AIRTABLE_APPOINTMENTS_TABLE", "")
CALL_RECORDING_TABLE = os.environ.get("AIRTABLE_CALL_RECORDING_TABLE", "")
CUSTOMERS_TABLE      = os.environ.get("AIRTABLE_CUSTOMERS_TABLE", "")

# Statuses that count as "active" bookings (can be rescheduled or cancelled)
ACTIVE_STATUSES = {"confirmed", "Confirmed", "Updated", "updated"}


def normalize_phone(phone: str) -> str:
    """
    Strip a phone number to its core local digits so that
    +971 54 372 5709, 054 372 5709, and 0543725709 all become 543725709,
    and +91 98765 43210 becomes 9876543210.
    """
    digits = re.sub(r"\D", "", phone)          # remove all non-digits
    if digits.startswith("971") and len(digits) - 3 == 9:
        digits = digits[3:]                    # strip UAE country code
    elif digits.startswith("91") and len(digits) - 2 == 10:
        digits = digits[2:]                    # strip India country code
    if digits.startswith("0"):
        digits = digits[1:]                    # strip leading zero (local UAE format)
    return digits


def _esc(value: str) -> str:
    """Escape single quotes in Airtable formula string literals to prevent formula injection."""
    return value.replace("'", "\\'")


def _api() -> Api:
    token = os.environ.get("AIRTABLE_TOKEN", "")
    if not token:
        raise RuntimeError("AIRTABLE_TOKEN is not set in .env")
    return Api(token)


def _base():
    base_id = os.environ.get("AIRTABLE_BASE_ID", "")
    if not base_id:
        raise RuntimeError("AIRTABLE_BASE_ID is not set in .env")
    return _api().base(base_id)


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

def find_latest_booking(phone: str) -> dict | None:
    """
    Return the most recently created active booking for this phone number,
    or None if not found.

    'Most recently created' = highest Airtable record creation order.
    We filter by Phone Number and active Booking Status, then take the last result.
    """
    phone = normalize_phone(phone)
    table = _base().table(APPOINTMENTS_TABLE)
    status_conditions = ", ".join('{Booking Status}="' + s + '"' for s in ACTIVE_STATUSES)
    formula = f"AND({{Phone Number}}='{_esc(phone)}', OR({status_conditions}))"
    records = table.all(formula=formula)
    if not records:
        return None
    # Airtable returns records in creation order ascending; last = most recent
    return records[-1]


def get_booking_by_id(record_id: str) -> dict | None:
    """Return a single appointment record by its Airtable record ID, or None if not found."""
    try:
        return _base().table(APPOINTMENTS_TABLE).get(record_id)
    except Exception as exc:
        if "404" in str(exc):
            return None
        raise


def create_booking(
    name: str,
    phone: str,
    address: str,
    service: str,
    starttime: str,
    endtime: str,
    issue_description: str,
    notes: str,
    technician_name: str,
    technician_calendar_id: str,
    technician_event_id: str,
    driver_name: str,
    driver_calendar_id: str,
    driver_event_id: str,
    call_recording_id: str = "",
) -> str:
    """Create a new booking record. Returns the Airtable record ID."""
    table = _base().table(APPOINTMENTS_TABLE)
    title = f"HVAC – {service} – {name}"
    description = (
        f"Technician: {technician_name}\n"
        f"Driver: {driver_name}\n"
        f"Service: {service}\n"
        f"Address: {address}\n"
        f"Issue: {issue_description}\n"
        f"Notes: {notes}"
    )
    phone = normalize_phone(phone)
    fields = {
        "Title": title,
        "Phone Number": phone,
        "Name": name,
        "Booking Status": "confirmed",
        "starttime": starttime,
        "endtime": endtime,
        "meetdescription": description,
        "Technician": technician_name,
        "Driver": driver_name,
        "TechnicianCalendarId": technician_calendar_id,
        "TechnicianEventId": technician_event_id,
        "DriverCalendarId": driver_calendar_id,
        "DriverEventId": driver_event_id,
    }
    if call_recording_id:
        fields["CallRecordingId"] = call_recording_id
    record = table.create(fields)
    return record["id"]


def update_booking_times(record_id: str, new_start: str, new_end: str) -> None:
    """Update the start/end times and set status to Updated."""
    table = _base().table(APPOINTMENTS_TABLE)
    table.update(record_id, {
        "starttime": new_start,
        "endtime": new_end,
        "Booking Status": "Updated",
    })


def cancel_booking(record_id: str) -> None:
    """Set the booking status to Canceled."""
    table = _base().table(APPOINTMENTS_TABLE)
    table.update(record_id, {"Booking Status": "Canceled"})


# ---------------------------------------------------------------------------
# Call recordings
# ---------------------------------------------------------------------------

def upsert_call_recording(
    call_id: str,
    cost: float | None,
    recording_url: str,
    transcript: str,
    customer_number: str,
    started_at: str,
    ended_at: str,
    call_length_secs: float | None,
    call_summary: str,
) -> None:
    """Insert or update a call recording record keyed by callrecording_id."""
    table = _base().table(CALL_RECORDING_TABLE)
    formula = f"{{callrecording_id}}='{_esc(call_id)}'"
    existing = table.all(formula=formula)

    fields = {
        "callrecording_id": call_id,
        "Call recording Url": recording_url,
        "transcript": transcript,
        "customer_Number": customer_number,
        "startedAt": started_at,
        "endedAt": ended_at,
        "callsummary": call_summary,
    }
    if cost is not None:
        fields["Cost"] = cost

    if existing:
        table.update(existing[0]["id"], fields)
    else:
        table.create(fields)


# ---------------------------------------------------------------------------
# Customers (returning caller memory)
# ---------------------------------------------------------------------------

def get_customer(phone: str) -> dict | None:
    """Return the customer profile for this phone number, or None if not found."""
    if not CUSTOMERS_TABLE:
        return None
    phone = normalize_phone(phone)
    table = _base().table(CUSTOMERS_TABLE)
    records = table.all(formula=f"{{Phone}}='{_esc(phone)}'")
    return records[0] if records else None


def upsert_customer(phone: str, name: str, address: str) -> None:
    """Create or update a customer profile after a confirmed booking."""
    if not CUSTOMERS_TABLE:
        return
    phone = normalize_phone(phone)
    table = _base().table(CUSTOMERS_TABLE)
    records = table.all(formula=f"{{Phone}}='{_esc(phone)}'")
    today = date.today().isoformat()
    if records:
        existing_fields = records[0]["fields"]
        table.update(records[0]["id"], {
            "Name": name,
            "Address": address,
            "LastBookingDate": today,
            "TotalBookings": existing_fields.get("TotalBookings", 0) + 1,
        })
    else:
        table.create({
            "Phone": phone,
            "Name": name,
            "Address": address,
            "LastBookingDate": today,
            "TotalBookings": 1,
        })
