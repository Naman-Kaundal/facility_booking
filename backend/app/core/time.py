"""Time helpers. Timestamps are stored in UTC; booking dates are institute-local (Asia/Kolkata)."""

from datetime import UTC, date, datetime, time, timedelta, timezone

# India has no daylight saving, so a fixed offset is exact (and needs no tzdata on Windows).
IST = timezone(timedelta(hours=5, minutes=30), name="IST")


def utc_now() -> datetime:
    return datetime.now(UTC)


def today_ist() -> date:
    return datetime.now(IST).date()


def start_of_day_ist(day: date) -> datetime:
    """The moment a booking date begins, as an aware datetime (used to pick the tariff in effect)."""
    return datetime.combine(day, time.min, tzinfo=IST)
