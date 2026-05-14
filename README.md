# AI Voice Appointment Setter

A production-grade AI voice receptionist built for a commercial HVAC company in Dubai. Developed and deployed as part of **Autonary**, a student-founded AI automation startup. The system is live and serving paying clients.

## What It Does

When a customer calls the business, an AI voice agent picks up, collects their details, checks real-time technician availability, and books, reschedules, or cancels appointments without any human involvement.

## Architecture

```
Inbound Call
     |
     v
  Vapi (Voice AI)
  GPT-4o, ElevenLabs TTS, Deepgram STT
     |
     v
  n8n Middleware
  n8n.autonary.site
     |
     v
  FastAPI Backend (localhost:8001)
     |
     |-- Google Calendar API (FreeBusy + Events)
     |-- Airtable (Bookings + Call Recordings)

Hosted on DigitalOcean. FastAPI runs on localhost only and is never publicly exposed.
```

## Tech Stack

| Layer | Technology |
|---|---|
| Voice AI | Vapi, GPT-4o, ElevenLabs, Deepgram |
| Middleware | Python, n8n |
| Backend | Python, FastAPI, Uvicorn |
| Scheduling | Google Calendar API (OAuth 2.0) |
| Database | Airtable |
| Infrastructure | DigitalOcean, systemd |
| Security | API key auth between middleware and backend |

## Key Engineering Decisions

**Atomic Booking**
/bookslots checks availability and confirms the booking in one operation. This prevents double-booking race conditions that would occur if checking and booking were separate steps.

**Batch FreeBusy Query**
All technician calendars are queried in a single Google Calendar API call rather than one call per technician. This keeps latency well within Vapi's 20-second tool call timeout.

**Skill-Based Technician Assignment**
Technicians are ranked by service specialization across three tiers: primary, secondary, and tertiary. The first available technician at the highest applicable tier gets assigned automatically.

**Service Normalization**
Natural language from callers such as "my AC is not cooling" gets mapped to internal service categories by the backend. This separates voice understanding from scheduling logic cleanly.

**Rollback on Failure**
If the driver calendar event creation fails after the technician event is already created, the technician event is deleted before returning an error. No orphaned calendar entries are left behind.

## Endpoints

| Endpoint | Purpose |
|---|---|
| POST /getslots | Check availability without booking |
| POST /bookslots | Atomic check, assign, and confirm |
| POST /updateslots | Reschedule by phone number |
| POST /cancelslots | Cancel and delete calendar events |
| POST /callresults | Save call transcript and recording |
| GET /health | Health check |

## Call Flows

**New Booking**
Agent collects name, phone, address, service type, and preferred time. Checks availability via GetSlots. On confirmation, BookSlots atomically assigns a technician and driver, creates Google Calendar events on both calendars, saves the record to Airtable, and confirms verbally.

**Reschedule**
Agent collects the new preferred time. GetSlots confirms availability. UpdateSlots patches both calendar events using stored event IDs and updates the Airtable record status.

**Cancellation**
Agent confirms cancellation intent. CancelSlots deletes both calendar events using stored event IDs. Airtable record is marked as Canceled only after successful calendar deletion.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# One-time Google OAuth setup, run locally only
python tools/auth_setup.py

# Run locally
uvicorn tools.server:app --port 8001 --reload

# Deploy to production
uvicorn tools.server:app --host 127.0.0.1 --port 8001
# Do not open port 8001 publicly
```

Copy .env.example to .env and fill in your credentials before running.

## Project Structure

```
|-- tools/
|   |-- server.py           FastAPI app, mounts all routers
|   |-- book_slot.py        Atomic booking and technician assignment
|   |-- get_slots.py        Availability checking
|   |-- update_slot.py      Reschedule logic with rollback
|   |-- cancel_slot.py      Cancellation with calendar cleanup
|   |-- call_results.py     End-of-call report handler
|   |-- calendar_utils.py   Google Calendar wrapper and batch FreeBusy
|   |-- airtable_utils.py   Airtable read and write utilities
|   |-- config.py           Technician roster, skill maps, service normalization
|   |-- auth_setup.py       Google OAuth 2.0 setup, run once locally
|-- appointment_setter.md   Full workflow documentation
|-- vapi_system_prompt.md   Voice agent system prompt
|-- requirements.txt
|-- .env.example
```

## Built By

**Arav Richhariya** -- Co-Founder, Autonary

AI automation startup providing intelligent solutions for local businesses in Dubai.

autonary.site
