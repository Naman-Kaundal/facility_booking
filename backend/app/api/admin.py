"""Admin endpoints (LLD §11.5). Every route requires an active ADMIN role, checked on the server."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import StaffContext, get_notifier, require_role
from app.db.session import get_db
from app.schemas.admin import (
    AdminAuditOut,
    AdminFacilityOut,
    EmailLogListOut,
    FacilityPatch,
    RetryOut,
    SettingsOut,
    SettingsPatch,
    SlotWindowPatch,
    StaffRoleIn,
    StaffRoleOut,
    StaffRolePatch,
    TariffIn,
    TariffPatch,
)
from app.services import admin_service
from app.services.notification_service import Notifier

router = APIRouter(prefix="/admin", tags=["admin"])
admin_only = require_role("ADMIN")


@router.get("/settings", response_model=SettingsOut)
def get_settings(_: StaffContext = Depends(admin_only), db: Session = Depends(get_db)) -> SettingsOut:
    return admin_service.settings_out(db)


@router.patch("/settings", response_model=SettingsOut)
def update_settings(
    body: SettingsPatch, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> SettingsOut:
    """GST %, cleaning %, security deposit, % of electricity in the advance, and the payment link."""
    return admin_service.update_settings(db, admin.user.email, body)


@router.get("/staff-roles", response_model=list[StaffRoleOut])
def list_staff_roles(_: StaffContext = Depends(admin_only), db: Session = Depends(get_db)) -> list[StaffRoleOut]:
    return admin_service.list_roles(db)


@router.post("/staff-roles", response_model=StaffRoleOut, status_code=201)
def grant_staff_role(
    body: StaffRoleIn, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> StaffRoleOut:
    return admin_service.add_role(db, admin.user.email, body)


@router.patch("/staff-roles/{role_id}", response_model=StaffRoleOut)
def update_staff_role(
    role_id: int, body: StaffRolePatch, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> StaffRoleOut:
    return admin_service.set_role_active(db, admin.user.email, role_id, body.active)


@router.get("/facilities", response_model=list[AdminFacilityOut])
def list_facilities(_: StaffContext = Depends(admin_only), db: Session = Depends(get_db)) -> list[AdminFacilityOut]:
    """Every facility, including inactive ones, with all slot windows and tariff versions."""
    return admin_service.list_facilities(db)


@router.patch("/facilities/{facility_id}", response_model=AdminFacilityOut)
def update_facility(
    facility_id: int, body: FacilityPatch, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> AdminFacilityOut:
    return admin_service.update_facility(db, admin.user.email, facility_id, body)


@router.post("/tariffs", response_model=AdminFacilityOut, status_code=201)
def add_tariff(
    body: TariffIn, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> AdminFacilityOut:
    """Add a new rate from a start date. Requests already submitted keep their old rate."""
    return admin_service.add_tariff(db, admin.user.email, body)


@router.patch("/tariffs/{tariff_id}", response_model=AdminFacilityOut)
def update_tariff(
    tariff_id: int, body: TariffPatch, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> AdminFacilityOut:
    return admin_service.set_tariff_active(db, admin.user.email, tariff_id, body.active)


@router.patch("/slot-windows/{slot_id}", response_model=AdminFacilityOut)
def update_slot_window(
    slot_id: int, body: SlotWindowPatch, admin: StaffContext = Depends(admin_only), db: Session = Depends(get_db)
) -> AdminFacilityOut:
    """Change a slot's label or times, or switch it off. Confirmed bookings keep their reserved times."""
    return admin_service.update_slot_window(db, admin.user.email, slot_id, body)


@router.get("/emails", response_model=EmailLogListOut)
def list_emails(
    status: Literal["PENDING", "SENT", "FAILED"] | None = Query(default=None),
    _: StaffContext = Depends(admin_only),
    db: Session = Depends(get_db),
    notifier: Notifier = Depends(get_notifier),
) -> EmailLogListOut:
    items = admin_service.list_emails(db, status)
    return EmailLogListOut(items=items, total=len(items), max_attempts=notifier.max_attempts)


@router.post("/emails/retry", response_model=RetryOut)
def retry_emails(_: StaffContext = Depends(admin_only), notifier: Notifier = Depends(get_notifier)) -> RetryOut:
    """Try again every failed email that still has attempts left."""
    report = notifier.retry_failed()
    return RetryOut(sent=report.sent, failed=report.failed, skipped=report.skipped)


@router.get("/audit", response_model=list[AdminAuditOut])
def admin_audit(_: StaffContext = Depends(admin_only), db: Session = Depends(get_db)) -> list[AdminAuditOut]:
    return admin_service.list_audit(db)
