"""Master data seeded into the database (LLD §5 and §6).

Amounts are in INR, taken from the week-3 presentation's tariff table.
"No charges" is stored as amount 0 with a display label, per LLD §5.2.

Items marked TO CONFIRM are placeholders that DR Facilities must confirm (LLD §19);
admins will be able to change them from Week 4 onwards.
"""

from datetime import UTC, datetime

# Effective date for the initial tariff version. Assumption: the presentation's
# tariffs apply from the start of 2026; change via admin master data later.
SEED_TARIFF_EFFECTIVE_FROM = datetime(2026, 1, 1, tzinfo=UTC)
# Tariff versions are identified by a string so the seed key never depends on datetime equality.
SEED_TARIFF_VERSION = "2026-presentation-v1"

CATEGORIES = ("PRIVATE", "GOVT", "IIT")
UNIT_LABELS = {
    "FULL_DAY": "full day",
    "HALF_DAY": "half day",
    "PER_DAY": "day",
    "THREE_HOUR": "3 hours",
}

# slot_types: the units a facility can be booked in. The LLD schema shows a single
# `slot_type`, but the Auditorium complete space is bookable as FULL_DAY *and*
# HALF_DAY, so a list is stored (documented in README).
FACILITIES: list[dict] = [
    {
        "code": "M3",
        "name": "LHC Classroom M3",
        "group": "LHC",
        "section": "ACADEMIC",
        "capacity": 100,
        "slot_types": ["FULL_DAY"],
        "sort_order": 10,
    },
    {
        "code": "M4",
        "name": "LHC Classroom M4",
        "group": "LHC",
        "section": "ACADEMIC",
        "capacity": 100,
        "slot_types": ["FULL_DAY"],
        "sort_order": 20,
    },
    {
        "code": "M5",
        "name": "LHC Classroom M5",
        "group": "LHC",
        "section": "ACADEMIC",
        "capacity": 150,
        "slot_types": ["FULL_DAY"],
        "sort_order": 30,
    },
    {
        "code": "M6",
        "name": "LHC Classroom M6",
        "group": "LHC",
        "section": "ACADEMIC",
        "capacity": 150,
        "slot_types": ["FULL_DAY"],
        "sort_order": 40,
    },
    {
        "code": "LHC_FOYER",
        "name": "LHC Foyer",
        "group": "LHC",
        "section": "ACADEMIC",
        "capacity": None,
        "slot_types": ["FULL_DAY"],
        "sort_order": 50,
    },
    {
        "code": "AUDI_COMPLETE",
        "name": "Auditorium complete space (hall + foyer)",
        "group": "AUDITORIUM",
        "section": "ACADEMIC",
        "capacity": None,
        "slot_types": ["FULL_DAY", "HALF_DAY"],
        "sort_order": 60,
    },
    {
        "code": "AUDI_FOYER",
        "name": "Auditorium foyer",
        "group": "AUDITORIUM",
        "section": "ACADEMIC",
        "capacity": None,
        "slot_types": ["FULL_DAY"],
        "sort_order": 70,
        "notes": "Slot duration to be confirmed by Facilities; shown as full day for now.",
    },
    {
        "code": "CRICKET",
        "name": "Cricket Ground",
        "group": "SPORTS",
        "section": "SPORTS",
        "capacity": None,
        "slot_types": ["PER_DAY"],
        "sort_order": 80,
    },
    {
        "code": "FOOTBALL",
        "name": "Football Ground",
        "group": "SPORTS",
        "section": "SPORTS",
        "capacity": None,
        "slot_types": ["THREE_HOUR"],
        "sort_order": 90,
    },
    {
        "code": "HOCKEY",
        "name": "Hockey Ground",
        "group": "SPORTS",
        "section": "SPORTS",
        "capacity": None,
        "slot_types": ["THREE_HOUR"],
        "sort_order": 100,
    },
]

# (facility code, unit) -> amounts by category. LLD §5.2 table.
TARIFFS: dict[tuple[str, str], dict[str, int]] = {
    ("M5", "FULL_DAY"): {"PRIVATE": 15000, "GOVT": 10000, "IIT": 7000},
    ("M6", "FULL_DAY"): {"PRIVATE": 15000, "GOVT": 10000, "IIT": 7000},
    ("M3", "FULL_DAY"): {"PRIVATE": 10000, "GOVT": 7000, "IIT": 5000},
    ("M4", "FULL_DAY"): {"PRIVATE": 10000, "GOVT": 7000, "IIT": 5000},
    ("LHC_FOYER", "FULL_DAY"): {"PRIVATE": 15000, "GOVT": 10000, "IIT": 7500},
    ("AUDI_COMPLETE", "FULL_DAY"): {"PRIVATE": 50000, "GOVT": 35000, "IIT": 25000},
    ("AUDI_COMPLETE", "HALF_DAY"): {"PRIVATE": 30000, "GOVT": 20000, "IIT": 15000},
    ("AUDI_FOYER", "FULL_DAY"): {"PRIVATE": 20000, "GOVT": 10000, "IIT": 5000},
    ("CRICKET", "PER_DAY"): {"PRIVATE": 10000, "GOVT": 8000, "IIT": 0},
    ("FOOTBALL", "THREE_HOUR"): {"PRIVATE": 3000, "GOVT": 2500, "IIT": 0},
    ("HOCKEY", "THREE_HOUR"): {"PRIVATE": 3000, "GOVT": 2500, "IIT": 0},
}

# Slot windows per slot type (LLD §6.1, §10.5). Times are 24h local (Asia/Kolkata).
# TO CONFIRM: half-day boundaries and the 3-hour sports inventory.
SLOT_WINDOWS_BY_TYPE: dict[str, list[dict]] = {
    "FULL_DAY": [{"slot_key": "FULL_DAY", "label": "Full day", "start": None, "end": None, "half": None}],
    "PER_DAY": [{"slot_key": "PER_DAY", "label": "Full day", "start": None, "end": None, "half": None}],
    "HALF_DAY": [
        {
            "slot_key": "FIRST_HALF",
            "label": "First half (09:00–13:00)",
            "start": "09:00",
            "end": "13:00",
            "half": "FIRST",
        },
        {
            "slot_key": "SECOND_HALF",
            "label": "Second half (14:00–18:00)",
            "start": "14:00",
            "end": "18:00",
            "half": "SECOND",
        },
    ],
    "THREE_HOUR": [
        {"slot_key": "09:00-12:00", "label": "09:00–12:00", "start": "09:00", "end": "12:00", "half": None},
        {"slot_key": "12:00-15:00", "label": "12:00–15:00", "start": "12:00", "end": "15:00", "half": None},
        {"slot_key": "15:00-18:00", "label": "15:00–18:00", "start": "15:00", "end": "18:00", "half": None},
    ],
}


def tariff_display_label(amount: int, unit: str) -> str:
    if amount == 0:
        return "No charges"
    return f"₹{amount:,} / {UNIT_LABELS[unit]}"
