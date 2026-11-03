"""Staff roles: which desks a signed-in user may use (LLD §3)."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import STAFF_ROLES, StaffRole

# Which section each desk role decides for.
SECTION_FOR_ROLE = {"ACADEMIC": "ACADEMIC", "SPORTS": "SPORTS"}


def active_roles(db: Session, email: str) -> list[str]:
    stmt = select(StaffRole.role).where(StaffRole.email == email.lower(), StaffRole.active.is_(True))
    return sorted(db.scalars(stmt))


def grant(db: Session, email: str, role: str, assigned_by: str | None = None) -> None:
    """Give (or re-activate) a role. Safe to run more than once."""
    role = role.upper()
    if role not in STAFF_ROLES:
        raise AppError("INVALID_ROLE", f"Role must be one of {', '.join(STAFF_ROLES)}.", 422)
    stmt = (
        insert(StaffRole)
        .values(email=email.strip().lower(), role=role, active=True, assigned_by=assigned_by)
        .on_conflict_do_update(constraint="uq_staff_roles_email_role", set_={"active": True})
    )
    db.execute(stmt)
    db.commit()


def revoke(db: Session, email: str, role: str) -> bool:
    """Deactivate a role (kept for the audit trail). Returns False if it wasn't assigned."""
    row = db.scalar(select(StaffRole).where(StaffRole.email == email.strip().lower(), StaffRole.role == role.upper()))
    if row is None:
        return False
    row.active = False
    db.commit()
    return True
