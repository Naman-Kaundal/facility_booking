"""Admin management of settings, staff roles and master data (LLD §3 ADMIN, §11.5).

Rules:
- Every change is written to ``admin_audit_events`` (who, what, before/after).
- Changes affect future bookings only: submitted requests keep their rate snapshots and costed
  requests keep their cost snapshot.
- Tariffs are never edited in place. A new rate is added with a start date; the rate it
  replaces is closed the moment the new one starts.
- An admin can't remove their own ADMIN role (so nobody locks the institute out by mistake).
"""

import json
import secrets
from datetime import datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import start_of_day_ist, today_ist, utc_now
from app.db.models import AdminAuditEvent, EmailLog, Facility, SlotWindow, StaffRole, Tariff
from app.db.seed_data import tariff_display_label
from app.schemas.admin import (
    AdminAuditOut,
    AdminFacilityOut,
    AdminSlotOut,
    AdminTariffOut,
    EmailLogOut,
    FacilityPatch,
    SettingsOut,
    SettingsPatch,
    SlotWindowPatch,
    StaffRoleIn,
    StaffRoleOut,
    TariffIn,
)
from app.services import roles_service, settings_service

WHOLE_DAY_TYPES = ("FULL_DAY", "PER_DAY")


def _audit(db: Session, actor: str, action: str, entity: str, entity_id, details: dict | None = None) -> None:
    db.add(
        AdminAuditEvent(
            actor_email=actor,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=json.dumps(details, default=str, ensure_ascii=False) if details else None,
        )
    )


def _hhmm(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value else None


# ----- settings -----


def settings_out(db: Session) -> SettingsOut:
    s = settings_service.get(db)
    return SettingsOut(
        gst_pct=float(s.gst_pct),
        cleaning_pct=float(s.cleaning_pct),
        security_deposit=s.security_deposit,
        electricity_advance_pct=float(s.electricity_advance_pct),
        payment_url=s.payment_url,
        updated_at=s.updated_at,
        updated_by=s.updated_by,
    )


def update_settings(db: Session, actor: str, data: SettingsPatch) -> SettingsOut:
    s = settings_service.get(db)
    changes = {}
    for field in ("gst_pct", "cleaning_pct", "security_deposit", "electricity_advance_pct"):
        value = getattr(data, field)
        if field in data.model_fields_set and value is not None and value != getattr(s, field):
            changes[field] = {"from": getattr(s, field), "to": value}
            setattr(s, field, value)
    if "payment_url" in data.model_fields_set:
        new_url = data.payment_url or None
        if new_url != s.payment_url:
            changes["payment_url"] = {"from": s.payment_url, "to": new_url}
            s.payment_url = new_url
    if changes:
        s.updated_by = actor
        s.updated_at = utc_now()
        _audit(db, actor, "SETTINGS_UPDATED", "settings", 1, changes)
    db.commit()
    return settings_out(db)


# ----- staff roles -----


def _role_out(row: StaffRole) -> StaffRoleOut:
    return StaffRoleOut(
        id=row.id, email=row.email, role=row.role, active=row.active,
        assigned_at=row.assigned_at, assigned_by=row.assigned_by,
    )


def list_roles(db: Session) -> list[StaffRoleOut]:
    rows = db.scalars(select(StaffRole).order_by(StaffRole.email, StaffRole.role))
    return [_role_out(r) for r in rows]


def add_role(db: Session, actor: str, data: StaffRoleIn) -> StaffRoleOut:
    email = data.email.strip().lower()
    roles_service.grant(db, email, data.role, assigned_by=actor)  # creates or re-activates
    row = db.scalar(select(StaffRole).where(StaffRole.email == email, StaffRole.role == data.role))
    _audit(db, actor, "ROLE_GRANTED", "staff_role", row.id, {"email": email, "role": data.role})
    db.commit()
    return _role_out(row)


def set_role_active(db: Session, actor: str, role_id: int, active: bool) -> StaffRoleOut:
    row = db.get(StaffRole, role_id)
    if row is None:
        raise AppError("NOT_FOUND", "Role assignment not found.", 404)
    if not active and row.role == "ADMIN" and row.email == actor.lower():
        raise AppError("CANNOT_REMOVE_OWN_ADMIN", "You can't remove your own admin role. Ask another admin.", 409)
    if row.active != active:
        row.active = active
        _audit(
            db, actor, "ROLE_ACTIVATED" if active else "ROLE_DEACTIVATED", "staff_role", row.id,
            {"email": row.email, "role": row.role},
        )
    db.commit()
    return _role_out(row)


# ----- facilities, tariffs, slot windows -----


def _facility_out(db: Session, facility: Facility, now: datetime) -> AdminFacilityOut:
    slots = db.scalars(
        select(SlotWindow).where(SlotWindow.facility_id == facility.id).order_by(SlotWindow.start_time, SlotWindow.id)
    ).all()
    tariffs = db.scalars(
        select(Tariff)
        .where(Tariff.facility_id == facility.id)
        .order_by(Tariff.unit, Tariff.category, Tariff.effective_from.desc(), Tariff.id.desc())
    ).all()
    return AdminFacilityOut(
        id=facility.id,
        code=facility.code,
        name=facility.name,
        group=facility.facility_group,
        section=facility.section,
        capacity=facility.capacity,
        notes=facility.notes,
        active=facility.active,
        sort_order=facility.sort_order,
        slot_types=sorted(st.slot_type for st in facility.slot_types),
        slots=[
            AdminSlotOut(
                id=s.id, slot_key=s.slot_key, slot_type=s.slot_type, label=s.label,
                start=_hhmm(s.start_time), end=_hhmm(s.end_time), active=s.active,
            )
            for s in slots
        ],
        tariffs=[
            AdminTariffOut(
                id=t.id, category=t.category, unit=t.unit, amount=t.amount, display_label=t.display_label,
                version=t.version, effective_from=t.effective_from, effective_to=t.effective_to, active=t.active,
                current=t.active and t.effective_from <= now and (t.effective_to is None or t.effective_to > now),
            )
            for t in tariffs
        ],
    )


def list_facilities(db: Session) -> list[AdminFacilityOut]:
    now = utc_now()
    facilities = db.scalars(select(Facility).order_by(Facility.sort_order, Facility.code)).all()
    return [_facility_out(db, f, now) for f in facilities]


def _facility(db: Session, facility_id: int) -> Facility:
    facility = db.get(Facility, facility_id)
    if facility is None:
        raise AppError("INVALID_FACILITY", "Facility not found.", 404)
    return facility


def update_facility(db: Session, actor: str, facility_id: int, data: FacilityPatch) -> AdminFacilityOut:
    facility = _facility(db, facility_id)
    changes = {}
    for field in data.model_fields_set:
        value = getattr(data, field)
        if value is None and field in ("name", "active", "sort_order"):
            continue  # these can't be blank
        if getattr(facility, field) != value:
            changes[field] = {"from": getattr(facility, field), "to": value}
            setattr(facility, field, value)
    if changes:
        _audit(db, actor, "FACILITY_UPDATED", "facility", facility.code, changes)
    db.commit()
    return _facility_out(db, facility, utc_now())


def add_tariff(db: Session, actor: str, data: TariffIn) -> AdminFacilityOut:
    facility = _facility(db, data.facility_id)
    if data.unit not in {st.slot_type for st in facility.slot_types}:
        raise AppError(
            "UNIT_NOT_SUPPORTED", f"{facility.name} can't be booked by {data.unit.replace('_', ' ').lower()}.", 422,
            {"field": "unit"},
        )
    if data.effective_from < today_ist():
        raise AppError("PAST_DATE", "A new rate can start today or later, not in the past.", 422,
                       {"field": "effective_from"})
    start = start_of_day_ist(data.effective_from)
    existing = db.scalars(
        select(Tariff).where(
            Tariff.facility_id == facility.id,
            Tariff.category == data.category,
            Tariff.unit == data.unit,
            Tariff.active.is_(True),
        )
    ).all()
    if any(t.effective_from >= start for t in existing):
        raise AppError(
            "TARIFF_CONFLICT", "A rate for this category already starts on or after that date. Deactivate it first.",
            409,
        )
    for t in existing:
        if t.effective_to is None or t.effective_to > start:
            t.effective_to = start  # the old rate stops when the new one starts
    tariff = Tariff(
        facility_id=facility.id,
        category=data.category,
        unit=data.unit,
        amount=data.amount,
        display_label=tariff_display_label(data.amount, data.unit),
        version=f"admin-{data.effective_from:%Y%m%d}-{secrets.token_hex(3)}",
        effective_from=start,
        effective_to=None,
    )
    db.add(tariff)
    db.flush()
    _audit(
        db, actor, "TARIFF_ADDED", "tariff", tariff.id,
        {"facility": facility.code, "category": data.category, "unit": data.unit, "amount": data.amount,
         "effective_from": data.effective_from},
    )
    db.commit()
    return _facility_out(db, facility, utc_now())


def set_tariff_active(db: Session, actor: str, tariff_id: int, active: bool) -> AdminFacilityOut:
    tariff = db.get(Tariff, tariff_id)
    if tariff is None:
        raise AppError("NOT_FOUND", "Tariff not found.", 404)
    if tariff.active != active:
        tariff.active = active
        _audit(db, actor, "TARIFF_ACTIVATED" if active else "TARIFF_DEACTIVATED", "tariff", tariff.id)
    db.commit()
    return _facility_out(db, _facility(db, tariff.facility_id), utc_now())


def update_slot_window(db: Session, actor: str, slot_id: int, data: SlotWindowPatch) -> AdminFacilityOut:
    slot = db.get(SlotWindow, slot_id)
    if slot is None:
        raise AppError("NOT_FOUND", "Slot not found.", 404)
    changes = {}
    if "start" in data.model_fields_set:
        if slot.slot_type in WHOLE_DAY_TYPES:
            raise AppError("WHOLE_DAY_SLOT", "Full-day slots cover the whole day and have no times.", 422)
        start = time.fromisoformat(data.start) if data.start else None
        end = time.fromisoformat(data.end) if data.end else None
        if start is None or end is None:
            raise AppError("TIMES_REQUIRED", "Give both the start and end time.", 422)
        if (start, end) != (slot.start_time, slot.end_time):
            before = f"{_hhmm(slot.start_time)}-{_hhmm(slot.end_time)}"
            changes["times"] = {"from": before, "to": f"{data.start}-{data.end}"}
            slot.start_time, slot.end_time = start, end
    if data.label is not None and data.label != slot.label:
        changes["label"] = {"from": slot.label, "to": data.label}
        slot.label = data.label
    if data.active is not None and data.active != slot.active:
        changes["active"] = {"from": slot.active, "to": data.active}
        slot.active = data.active
    if changes:
        _audit(db, actor, "SLOT_UPDATED", "slot_window", slot.id, changes)
    db.commit()
    return _facility_out(db, _facility(db, slot.facility_id), utc_now())


# ----- emails and audit -----


def list_emails(db: Session, status: str | None, limit: int = 200) -> list[EmailLogOut]:
    stmt = select(EmailLog).order_by(EmailLog.id.desc()).limit(limit)
    if status:
        stmt = stmt.where(EmailLog.status == status)
    return [
        EmailLogOut(
            id=e.id, request_id=e.request_id, event=e.event, recipient=e.recipient, subject=e.subject,
            status=e.status, attempt_count=e.attempt_count, last_error=e.last_error, created_at=e.created_at,
            last_attempt_at=e.last_attempt_at, sent_at=e.sent_at,
        )
        for e in db.scalars(stmt)
    ]


def list_audit(db: Session, limit: int = 200) -> list[AdminAuditOut]:
    rows = db.scalars(select(AdminAuditEvent).order_by(AdminAuditEvent.id.desc()).limit(limit))
    return [
        AdminAuditOut(
            id=r.id, actor_email=r.actor_email, action=r.action, entity=r.entity, entity_id=r.entity_id,
            details=r.details, created_at=r.created_at,
        )
        for r in rows
    ]
