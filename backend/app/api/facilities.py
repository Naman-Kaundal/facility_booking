from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.repositories.facilities import FacilityRepository
from app.schemas.facility import FacilityListOut, FacilityOut
from app.services.facility_service import FacilityService

router = APIRouter(prefix="/facilities", tags=["facilities"])


def get_facility_service(db: Session = Depends(get_db)) -> FacilityService:
    return FacilityService(FacilityRepository(db))


@router.get("", response_model=FacilityListOut)
def list_facilities(
    active: bool = Query(True, description="Return active (true) or inactive (false) facilities."),
    service: FacilityService = Depends(get_facility_service),
) -> FacilityListOut:
    items = service.list_catalogue(active=active)
    return FacilityListOut(items=items, total=len(items))


@router.get("/{code}", response_model=FacilityOut)
def get_facility(code: str, service: FacilityService = Depends(get_facility_service)) -> FacilityOut:
    return service.get_by_code(code)
