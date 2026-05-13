"""
Google Calendar helpers.

Authentication: OAuth 2.0 using credentials.json + token.json in the project root.
- credentials.json  — downloaded from Google Cloud Console (OAuth client for Desktop app)
- token.json        — generated once by running: python tools/auth_setup.py

The token auto-refreshes as long as the refresh_token is present.
"""

import os
import tempfile
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
DUBAI_TZ = timezone(timedelta(hours=4))


def validate_time_window(starttime: str, endtime: str) -> str | None:
    """
    Validate a time window before sending it to Google Calendar.
    Returns None if valid, or an error string describing the problem.
    """
    try:
        start_dt = datetime.fromisoformat(starttime)
    except ValueError:
        return f"invalid_starttime_format: {starttime!r}"
    try:
        end_dt = datetime.fromisoformat(endtime)
    except ValueError:
        return f"invalid_endtime_format: {endtime!r}"

    start_aware = start_dt if start_dt.tzinfo else start_dt.replace(tzinfo=DUBAI_TZ)
    end_aware = end_dt if end_dt.tzinfo else end_dt.replace(tzinfo=DUBAI_TZ)
    start_aware = start_aware.astimezone(DUBAI_TZ)
    end_aware = end_aware.astimezone(DUBAI_TZ)

    if end_aware <= start_aware:
        return "endtime_not_after_starttime"

    duration = end_aware - start_aware
    if duration < timedelta(minutes=30):
        return f"slot_too_short: {int(duration.total_seconds() / 60)} min"
    if duration > timedelta(hours=4):
        return f"slot_too_long: {int(duration.total_seconds() / 3600)} hrs"

    now_dubai = datetime.now(tz=DUBAI_TZ)
    if start_aware < now_dubai + timedelta(minutes=15):
        return "starttime_too_soon_or_in_past"

    return None


_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(_HERE, "credentials.json")
TOKEN_FILE = os.path.join(_HERE, "token.json")


def _get_service():
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "token.json not found. Run: python tools/auth_setup.py  (once, on your local machine)"
        )
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            import logging as _logging
            _logging.getLogger(__name__).info("Google token expired — refreshing")
            creds.refresh(Request())
            tmp_fd, tmp_path = tempfile.mkstemp(dir=os.path.dirname(TOKEN_FILE), suffix=".tmp")
            try:
                with os.fdopen(tmp_fd, "w") as f:
                    f.write(creds.to_json())
                os.replace(tmp_path, TOKEN_FILE)
            except Exception:
                os.unlink(tmp_path)
                raise
        else:
            raise RuntimeError(
                "Google credentials are invalid and cannot be auto-refreshed. "
                "Re-run: python tools/auth_setup.py"
            )
    return build("calendar", "v3", credentials=creds)


def is_calendar_free(calendar_id: str, start: str, end: str) -> bool:
    """
    Return True if the calendar has no events overlapping [start, end].
    start/end are ISO 8601 strings with timezone offset, e.g. '2026-03-21T16:00:00+04:00'.
    """
    service = _get_service()
    body = {
        "timeMin": start,
        "timeMax": end,
        "items": [{"id": calendar_id}],
    }
    result = service.freebusy().query(body=body).execute()
    busy_slots = result["calendars"][calendar_id]["busy"]
    return len(busy_slots) == 0


def batch_freebusy(calendar_ids: list[str], start: str, end: str) -> set[str]:
    """
    Return the set of calendar IDs that are BUSY in [start, end].
    Queries all calendars in a single API call instead of one call per calendar.
    """
    service = _get_service()
    body = {
        "timeMin": start,
        "timeMax": end,
        "items": [{"id": cal_id} for cal_id in calendar_ids],
    }
    result = service.freebusy().query(body=body).execute()
    return {
        cal_id
        for cal_id in calendar_ids
        if result["calendars"][cal_id]["busy"]
    }


def create_event(calendar_id: str, summary: str, description: str, start: str, end: str) -> str:
    """
    Create a calendar event and return the event ID.
    start/end are ISO 8601 strings.
    """
    service = _get_service()
    event = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start},
        "end":   {"dateTime": end},
    }
    created = service.events().insert(calendarId=calendar_id, body=event).execute()
    return created["id"]


def update_event(calendar_id: str, event_id: str, new_start: str, new_end: str) -> None:
    """Patch an existing event with a new start/end time."""
    service = _get_service()
    patch = {
        "start": {"dateTime": new_start},
        "end":   {"dateTime": new_end},
    }
    service.events().patch(calendarId=calendar_id, eventId=event_id, body=patch).execute()


def delete_event(calendar_id: str, event_id: str) -> None:
    """
    Delete a calendar event. Silently ignores 404 (already deleted / never existed).
    Raises on any other error.
    """
    service = _get_service()
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return
        raise
