# Technician and driver rosters, service normalization map.
# Edit skill assignments here as the team's roles evolve.
#
# All calendar IDs are loaded from environment variables.
# See .env.example for the full list of required variables.

import os
import re
from dotenv import load_dotenv

load_dotenv()


def _cal_env_key(prefix: str, name: str) -> str:
    return prefix + "_" + re.sub(r"[^A-Z0-9]+", "_", name.upper()).strip("_")


# ---------------------------------------------------------------------------
# Technician roster
# Add or remove technicians here. Each entry needs:
#   name        — used in calendar event summaries and Airtable records
#   calendar_id — Google Calendar ID, loaded from environment variable
#   primary     — service category this technician is best at
#   secondary   — second-best service category
#   tertiary    — fallback service category
# ---------------------------------------------------------------------------

TECHNICIANS = [
    # AC Repair Specialists
    {
        "name": "Technician_1",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_1", ""),
        "primary": "ac_repair", "secondary": "ac_maintenance", "tertiary": "duct_cleaning",
    },
    # AC Maintenance Specialists
    {
        "name": "Technician_2",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_2", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_3",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_3", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_4",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_4", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_5",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_5", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_6",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_6", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_7",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_7", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_8",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_8", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    {
        "name": "Technician_9",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_9", ""),
        "primary": "ac_maintenance", "secondary": "ac_repair", "tertiary": "duct_cleaning",
    },
    # Duct Cleaning Specialists
    {
        "name": "Technician_10",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_10", ""),
        "primary": "duct_cleaning", "secondary": "ac_maintenance", "tertiary": "ac_repair",
    },
    {
        "name": "Technician_11",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_11", ""),
        "primary": "duct_cleaning", "secondary": "ac_maintenance", "tertiary": "ac_repair",
    },
    {
        "name": "Technician_12",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_12", ""),
        "primary": "duct_cleaning", "secondary": "ac_maintenance", "tertiary": "ac_repair",
    },
    # Electricians
    {
        "name": "Technician_13",
        "calendar_id": os.getenv("TECH_CAL_ID_TECHNICIAN_13", ""),
        "primary": "electrical", "secondary": "ac_repair", "tertiary": "ac_maintenance",
    },
]

# ---------------------------------------------------------------------------
# Driver roster
# ---------------------------------------------------------------------------

DRIVERS = [
    {"name": "Driver_1", "calendar_id": os.getenv("DRIVER_CAL_ID_DRIVER_1", "")},
    {"name": "Driver_2", "calendar_id": os.getenv("DRIVER_CAL_ID_DRIVER_2", "")},
    {"name": "Driver_3", "calendar_id": os.getenv("DRIVER_CAL_ID_DRIVER_3", "")},
    {"name": "Driver_4", "calendar_id": os.getenv("DRIVER_CAL_ID_DRIVER_4", "")},
    {"name": "Driver_5", "calendar_id": os.getenv("DRIVER_CAL_ID_DRIVER_5", "")},
]

# ---------------------------------------------------------------------------
# Service normalization map
# Maps substrings from caller's free-text service description → internal category.
# Checked in order; first match wins. More specific phrases go first.
# ---------------------------------------------------------------------------

SERVICE_MAP = [
    # duct_cleaning
    ("deep clean",    "duct_cleaning"),
    ("deep cleaning", "duct_cleaning"),
    ("duct",          "duct_cleaning"),
    ("coil",          "duct_cleaning"),
    ("vent",          "duct_cleaning"),
    # ac_repair
    ("not cooling",   "ac_repair"),
    ("not working",   "ac_repair"),
    ("water drip",    "ac_repair"),
    ("breakdown",     "ac_repair"),
    ("ac repair",     "ac_repair"),
    ("leak",          "ac_repair"),
    ("smell",         "ac_repair"),
    ("noise",         "ac_repair"),
    # electrical
    ("electric",      "electrical"),
    ("wiring",        "electrical"),
    ("socket",        "electrical"),
    ("switch",        "electrical"),
    ("fuse",          "electrical"),
    ("circuit",       "electrical"),
    ("power outage",  "electrical"),
    # plumbing
    ("plumb",         "plumbing"),
    ("pipe",          "plumbing"),
    ("tap",           "plumbing"),
    ("drain",         "plumbing"),
    ("toilet",        "plumbing"),
    ("shower",        "plumbing"),
    ("sink",          "plumbing"),
    ("flush",         "plumbing"),
    ("water leak",    "plumbing"),
    # painting
    ("paint",         "painting"),
    # carpentry
    ("carpent",       "carpentry"),
    ("door",          "carpentry"),
    ("cabinet",       "carpentry"),
    ("furniture",     "carpentry"),
    ("wood",          "carpentry"),
    ("wardrobe",      "carpentry"),
    # civil_work
    ("brick",         "civil_work"),
    ("tile",          "civil_work"),
    ("tiling",        "civil_work"),
    ("stone",         "civil_work"),
    ("mason",         "civil_work"),
    ("civil",         "civil_work"),
    ("floor",         "civil_work"),
    ("ceiling",       "civil_work"),
    ("crack",         "civil_work"),
    ("wall",          "civil_work"),
    # ac_maintenance (broadest terms — keep last)
    ("annual",        "ac_maintenance"),
    ("yearly",        "ac_maintenance"),
    ("maintenance",   "ac_maintenance"),
    ("filter",        "ac_maintenance"),
    ("gas",           "ac_maintenance"),
    ("check",         "ac_maintenance"),
    ("service",       "ac_maintenance"),
    ("cleaning",      "ac_maintenance"),
    ("water",         "ac_repair"),
]

SKILL_LEVELS = ("primary", "secondary", "tertiary")


def normalize_service(text: str) -> str:
    """Map a free-text service description to an internal category."""
    lower = text.lower()
    for keyword, category in SERVICE_MAP:
        if keyword in lower:
            return category
    return "ac_maintenance"  # safe default


def ranked_technicians(service_category: str) -> list[dict]:
    """Return bookable technicians (those with a calendar_id) sorted by skill match."""
    order = {level: i for i, level in enumerate(SKILL_LEVELS)}
    def skill_rank(tech):
        for level in SKILL_LEVELS:
            if tech[level] == service_category:
                return order[level]
        return len(SKILL_LEVELS)
    bookable = [t for t in TECHNICIANS if "@" in t.get("calendar_id", "")]
    return sorted(bookable, key=skill_rank)
