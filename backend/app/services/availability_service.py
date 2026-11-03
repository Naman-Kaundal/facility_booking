"""Slot availability and confirmed-booking reservations (LLD §6.2).

Rules:
- Only CONFIRMED lines reserve time. Drafts and pending lines never hold a slot, so an
  abandoned draft can't block anyone (LLD's recommended hold policy).
- A slot without times (full day / per day) covers the whole day.
- Availability is checked when a request is submitted and again, atomically, when a
  section confirms a line. The final guard is the PostgreSQL exclusion constraint on
  ``reservations``, so two overlapping confirmations can never both succeed.
"""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Facility, RequestLine, Reservation, SlotWindow
from app.repositories.facilities import FacilityRepository
from app.schemas.availability import AvailabilityOut, SlotAvailabilityOut


def slot_range(day: date, slot: SlotWindow) -> Range[datetime]:
    """The [start, end) wall-clock range a slot occupies on a date."""
    if slot.start_time is None or slot.end_time is None:
        start = datetime.combine(day, time.min)
        return Range(start, start + timedelta(days=1), bounds="[)")
    return Range(datetime.combine(day, slot.start_time), datetime.combine(day, slot.end_time), bounds="[)")


def _overlaps(a: Range[datetime], b: Range[datetime]) -> bool:
    return a.lower < b.upper and b.lower < a.upper


def _day_range(day: date) -> Range[datetime]:
    start = datetime.combine(day, time.min)
    return Range(start, start + timedelta(days=1), bounds="[)")


class AvailabilityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.facilities = FacilityRepository(db)

    def reservations_on(self, facility_id: int, day: date) -> list[Reservation]:
        stmt = select(Reservation).where(
            Reservation.facility_id == facility_id, Reservation.during.overlaps(_day_range(day))
        )
        return list(self.db.scalars(stmt))

    def is_free(self, facility_id: int, day: date, slot: SlotWindow, exclude_line_id: int | None = None) -> bool:
        wanted = slot_range(day, slot)
        return not any(
            _overlaps(wanted, r.during)
            for r in self.reservations_on(facility_id, day)
            if r.request_line_id != exclude_line_id
        )

    def for_facility(self, facility_id: int, day: date) -> AvailabilityOut:
        facility: Facility | None = self.facilities.get(facility_id)
        if facility is None or not facility.active:
            raise AppError("INVALID_FACILITY", "That facility is not available for booking.", 404)
        booked = [r.during for r in self.reservations_on(facility_id, day)]
        windows = sorted(
            self.facilities.active_slot_windows_for([facility_id]),
            key=lambda w: (w.start_time or time.min, w.slot_key),
        )
        slots = []
        for w in windows:
            taken = any(_overlaps(slot_range(day, w), b) for b in booked)
            slots.append(
                SlotAvailabilityOut(
                    slot_key=w.slot_key,
                    label=w.label,
                    slot_type=w.slot_type,
                    start=w.start_time.strftime("%H:%M") if w.start_time else None,
                    end=w.end_time.strftime("%H:%M") if w.end_time else None,
                    available=not taken,
                    unavailable_reason="Already booked" if taken else None,
                )
            )
        return AvailabilityOut(facility_id=facility_id, date=day, slots=slots)

    def reserve(self, line: RequestLine) -> Reservation:
        """Reserve a line's slot, or raise SLOT_UNAVAILABLE if anything overlapping is confirmed.

        Uses a savepoint so a clash only undoes this insert, and relies on the database's
        exclusion constraint so concurrent confirmations are safe.
        """
        reservation = Reservation(
            request_line_id=line.id,
            facility_id=line.facility_id,
            during=slot_range(line.booking_date, line.slot),
        )
        try:
            with self.db.begin_nested():
                self.db.add(reservation)
                self.db.flush()
        except IntegrityError as exc:
            raise AppError(
                "SLOT_UNAVAILABLE",
                f"{line.facility.name} is already booked at that time on {line.booking_date:%d %b %Y}.",
                409,
                {"line_id": line.id},
            ) from exc
        return reservation
