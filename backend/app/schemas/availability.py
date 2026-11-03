from datetime import date

from pydantic import BaseModel

from app.schemas.facility import Unit


class SlotAvailabilityOut(BaseModel):
    slot_key: str
    label: str
    slot_type: Unit
    start: str | None
    end: str | None
    available: bool
    unavailable_reason: str | None = None


class AvailabilityOut(BaseModel):
    facility_id: int
    date: date
    slots: list[SlotAvailabilityOut]
