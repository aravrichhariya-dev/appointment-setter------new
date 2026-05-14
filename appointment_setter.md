# Workflow: LiwaSun HVAC AI Appointment Setter

## Objective
Handle inbound calls for LiwaSun HVAC (Dubai). Collect customer details, check technician
availability, book/reschedule/cancel appointments, and save all records to Airtable and
Google Calendar.

## System Overview
- **Voice layer**: Vapi — assistant "Max" (GPT-4o, ElevenLabs TTS, Deepgram nova-2 transcription)
- **Middleware**: Python workflow server on `n8n.autonary.site` — receives Vapi webhooks, forwards to FastAPI
- **Backend**: Python FastAPI server (`tools/server.py`) on `127.0.0.1:8001` (localhost only)
- **Calendar**: Google Calendar (13 technician + 5 driver calendars)
- **Database**: Airtable base `appOA2UwokFeHnemS`
- **Production host**: DigitalOcean `157.230.105.23` — runs both the middleware and FastAPI on the same droplet

**Request flow**: Vapi → n8n.autonary.site (Python middleware) → localhost:8001 (FastAPI)
FastAPI is never exposed publicly. The middleware calls it on localhost.

---

## Endpoints

| Vapi Tool | n8n route | FastAPI endpoint | Purpose |
|---|---|---|---|
| GetSlots2 | /getslots | POST /getslots | Check if a technician is free (fast, no booking) |
| BookSlots2 | /bookslots | POST /bookslots | Atomic check + assign + book |
| UpdateSlots2 | /updateslots | POST /updateslots | Reschedule by phone number |
| CancelSlots2 | /cancelslots | POST /cancelslots | Cancel by phone number |
| (assistant server) | /callresults | POST /callresults | Save end-of-call report |

---

## Call Flows

### New Booking
1. Max collects: name, phone, address, service type, preferred time
2. Max calls **GetSlots** (service + starttime + endtime) → `available` or `no_technician_available_for_that_time`
3. If available, caller confirms → Max calls **BookSlots** with all fields
4. BookSlots re-checks availability atomically, assigns first free tech + first free driver
5. Creates Google Calendar events on both calendars
6. Saves booking to Airtable with status `confirmed`
7. Returns `confirmed` → Max confirms verbally

### Reschedule
1. Max collects: phone, new time
2. Max calls **GetSlots** for new time → must return `available`
3. If available → Max calls **UpdateSlots** (phone + Rescheduled_starttime + Rescheduled_endttime)
4. UpdateSlots fetches stored event IDs from Airtable, patches both calendar events, updates status to `Updated`
5. Returns `Confirmed`

### Cancellation
1. Max confirms caller wants to cancel (not reschedule)
2. Max calls **CancelSlots** (phone)
3. CancelSlots fetches event IDs from Airtable, deletes both calendar events (404 = ok)
4. Sets Airtable status to `Canceled` **only after** calendar deletions succeed
5. Returns `Canceled`

### End of Call
- Vapi sends end-of-call-report to assistant-level `server.url` → n8n → `/callresults`
- Saves to Call Recording table: transcript, recording URL, cost, duration, summary

---

## Service Normalization
Max passes the caller's words (e.g. "my AC is not cooling"). The backend maps to:
- `duct_cleaning` — duct, deep clean, coil, vent
- `ac_repair` — repair, not cooling, not working, leak, smell, noise, water, breakdown
- `ac_maintenance` — maintenance, filter, gas, service, check, annual, yearly, cleaning (default fallback)

---

## Technician Assignment
Technicians are ranked by skill priority (primary > secondary > tertiary) for the requested
service. First available wins. With 13 technicians there is almost always a free tech.
Availability is checked in a single batch FreeBusy API call across all calendars.

Priority tiers:
- **ac_repair primary**: Ravi Kumar, Abdul Gbla
- **ac_maintenance primary**: Mukadih Hussain, Sayad Akip, Manoj Bari, Sanjay Chauhan, MASUD HOSSAIN HARUNUR, MUHAMMAED SALMAN, Raj Kapoor, SHAHBAZ PATEL IQBAL
- **duct_cleaning primary**: MD HASIM, RAMJANIK, MD Kalam

---

## Error Codes Max Must Handle

| Code | Meaning | Max's response |
|---|---|---|
| `available` | Slot is open | Confirm time, proceed to booking |
| `no_technician_available_for_that_time` | No tech free (GetSlots) | Ask for different time |
| `no_available_technician` | No tech free (BookSlots) | Race condition — ask for different time |
| `no_available_driver` | All drivers busy | Ask for different time |
| `booking_not_found` | No active booking for that phone | Ask for different number |
| `missing_required_fields` | Backend missing data | Ask caller for the missing info |
| `calendar_error: ...` | Google API or Airtable failure | Apologise, ask to try again |
| `confirmed` | Booking created | Confirm appointment verbally |
| `Confirmed` | Booking rescheduled | Confirm new time verbally |
| `Canceled` | Booking canceled | Confirm cancellation verbally |

---

## Setup & Running

### Prerequisites
1. Google OAuth 2.0 credentials
   - Download `credentials.json` from Google Cloud Console (OAuth client for Desktop app)
   - Run `python tools/auth_setup.py` once on your local machine → generates `token.json`
   - Copy both `credentials.json` and `token.json` to the production server alongside the code
   - Share all 18 calendars (13 tech + 5 driver) with the Google account (Editor role)
2. Airtable personal access token with `data.records:read` and `data.records:write` scopes
   - Set as `AIRTABLE_TOKEN` in `.env`
3. API secret for middleware→FastAPI auth
   - Set `API_SECRET` to any strong random string in `.env`
   - Add the same value as an `x-api-key` header in every outbound request your middleware makes to FastAPI

### Install dependencies
```bash
cd "Liwasun Python"
python -m venv .venv
.venv/Scripts/activate    # Windows
source .venv/bin/activate # Linux/Mac
pip install -r requirements.txt
```

### Run locally
```bash
uvicorn tools.server:app --port 8001 --reload
```

### Test locally with ngrok
```bash
ngrok http 8001
# Copy the https URL, e.g. https://abc123.ngrok.io
# In n8n, temporarily point all HTTP nodes to:
#   https://abc123.ngrok.io/getslots
#   https://abc123.ngrok.io/bookslots
#   https://abc123.ngrok.io/updateslots
#   https://abc123.ngrok.io/cancelslots
#   https://abc123.ngrok.io/callresults
```

### Deploy to DigitalOcean (same droplet as n8n)
```bash
ssh root@157.230.105.23
# copy code, install deps, ensure credentials.json + token.json are present
uvicorn tools.server:app --host 127.0.0.1 --port 8001
# Do NOT run ufw allow 8001 — port must stay closed to the public
# n8n calls FastAPI on localhost:8001 internally
```

### Health check
```
GET http://localhost:8001/health  →  {"status": "ok"}
```

---

## Debugging

### Where to find logs

**FastAPI server (primary log source)**
All output goes to uvicorn stdout. On the DigitalOcean droplet:
```bash
ssh root@157.230.105.23
journalctl -u liwasun -n 200 --no-pager   # if running as a systemd service
# or, if running in a screen/tmux session:
screen -r   # or: tmux attach
```
Every inbound request, tool dispatch, and unhandled exception prints here. Read the full traceback — it will name the exact file and line.

**Python middleware (n8n.autonary.site)**
Logs live on the same droplet. Check whatever process manager runs it (systemd, screen, pm2). If the middleware is silently dropping requests, look here first before suspecting FastAPI.

---

### Airtable — inspect booking state

Base ID: `appOA2UwokFeHnemS`
- Appointments table: `tblF8LF9lmkHMbk7v`
- Call recordings table: `tbl1b6vMhq9IT9JEZ`

To pull a record directly in Python (from project root):
```python
from tools.airtable_utils import find_latest_booking, find_booking_by_phone
rec = find_latest_booking("0501234567")  # returns most recent active record
print(rec["fields"])
# Key fields: Booking Status, Technician, Driver, TechnicianEventId, DriverEventId, starttime
```
`Booking Status` values: `confirmed`, `Updated`, `Canceled`
If a booking shows `confirmed` but the caller says it wasn't made → calendar event IDs are in the record; use them to verify the calendar directly.

---

### Google Calendar — inspect events

Calendar event IDs are stored in Airtable as `TechnicianEventId` and `DriverEventId`.
To check or delete an event manually:
```python
from tools.calendar_utils import _get_service
svc = _get_service()
event = svc.events().get(calendarId="<tech_calendar_id>", eventId="<TechnicianEventId>").execute()
print(event["start"], event["summary"])
```
Tech and driver calendar IDs are in `tools/config.py` under `TECH_CALENDARS` and `DRIVER_CALENDARS`.

---

### Key files by symptom

| Symptom | File to read |
|---|---|
| Booking returns wrong error code | `tools/book_slot.py` |
| Wrong technician assigned / wrong skill match | `tools/book_slot.py` → `assign_technician()`, `tools/config.py` → skill maps |
| Availability check wrong | `tools/get_slots.py`, `tools/calendar_utils.py` → `batch_freebusy()` |
| Reschedule fails or patches wrong event | `tools/update_slot.py` |
| Cancel doesn't delete calendar event | `tools/cancel_slot.py` |
| Call recording not saved | `tools/call_results.py` |
| Airtable read/write failure | `tools/airtable_utils.py` |
| Server not starting / endpoint 404 | `tools/server.py` |
| Google auth expired | re-run `tools/auth_setup.py` locally, redeploy `token.json` |

---

### Run the test suite as a diagnostic

```bash
# targets production directly (skips middleware)
python tools/test_suite.py

# targets local instance
python tools/test_suite.py --host localhost:8001
```
All tests use phone numbers `0501111001`, `0501111010`–`0501111017`, `0501111020`, and date `2026-04-15`. They self-clean on success. If a test fails mid-run, those phone numbers may have orphaned records in Airtable and calendar events on `2026-04-15` — cancel them manually via `/cancelslots` or delete directly from Airtable.

---

### Common failure patterns

| Symptom | Likely cause |
|---|---|
| `calendar_error: airtable save failed` | `AIRTABLE_TOKEN` expired or wrong scope |
| `calendar_error: Google API ...` | `token.json` expired — re-run `auth_setup.py` |
| `booking_not_found` when record exists | Record has `Booking Status = Canceled`; `find_booking_by_phone` only returns active records |
| `no_available_technician` on a quiet day | Check `config.py` skill maps — service may have normalized to wrong category |
| Middleware gets 401 from FastAPI | `x-api-key` header value doesn't match `API_SECRET` in `.env` |
| Tool call times out (Vapi 20s limit) | Google FreeBusy call hung — check Calendar API quota in Google Cloud Console |

---

## Known Constraints
- Vapi timeout per tool call is 20 seconds. Batch FreeBusy queries all 13 tech calendars in a single API call (`batch_freebusy` in `tools/calendar_utils.py`), keeping latency well within budget.
- All times must be ISO 8601 with `+04:00` Dubai offset.
- Operating hours 10:00–21:00 Dubai time are enforced by Max's system prompt, not this backend.
- Token refresh is automatic (`token.json` refresh token). If the refresh token is ever revoked, re-run `auth_setup.py` and redeploy `token.json`.
- `Rescheduled_endttime` (double-t) in the UpdateSlots2 Vapi schema is intentional — it matches the field name expected by `tools/update_slot.py`.
