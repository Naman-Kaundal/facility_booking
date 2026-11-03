from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.availability import AvailabilityOut
from app.services.availability_service import AvailabilityService

router = APIRouter(tags=["availability"])


@router.get("/availability", response_model=AvailabilityOut)
def get_availability(
    facility_id: int = Query(..., gt=0),
    day: date = Query(..., alias="date", description="Booking date, YYYY-MM-DD"),
    db: Session = Depends(get_db),
) -> AvailabilityOut:
    """Which of a facility's slots are free on a date. Only confirmed bookings make a slot unavailable."""
    return AvailabilityService(db).for_facility(facility_id, day)
