"""Database access for facilities, tariffs and slot windows."""

from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Facility, SlotWindow, Tariff


class FacilityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_facilities(self, active: bool | None = True) -> list[Facility]:
        stmt = select(Facility).order_by(Facility.sort_order, Facility.code)
        if active is not None:
            stmt = stmt.where(Facility.active.is_(active))
        return list(self.session.scalars(stmt))

    def get_by_code(self, code: str) -> Facility | None:
        return self.session.scalars(select(Facility).where(Facility.code == code)).first()

    def effective_tariffs_for(self, facility_ids: list[int], at: datetime) -> list[Tariff]:
        """Active tariffs whose effective window contains ``at``."""
        stmt = select(Tariff).where(
            Tariff.facility_id.in_(facility_ids),
            Tariff.active.is_(True),
            Tariff.effective_from <= at,
            or_(Tariff.effective_to.is_(None), Tariff.effective_to > at),
        )
        return list(self.session.scalars(stmt))

    def active_slot_windows_for(self, facility_ids: list[int]) -> list[SlotWindow]:
        stmt = select(SlotWindow).where(SlotWindow.facility_id.in_(facility_ids), SlotWindow.active.is_(True))
        return list(self.session.scalars(stmt))

    def get(self, facility_id: int) -> Facility | None:
        return self.session.get(Facility, facility_id)

    def get_slot(self, facility_id: int, slot_key: str) -> SlotWindow | None:
        return self.session.scalars(
            select(SlotWindow).where(SlotWindow.facility_id == facility_id, SlotWindow.slot_key == slot_key)
        ).first()

    def effective_tariff(self, facility_id: int, category: str, unit: str, at: datetime) -> Tariff | None:
        """The newest active tariff for this facility/category/unit in effect at ``at``."""
        stmt = (
            select(Tariff)
            .where(
                Tariff.facility_id == facility_id,
                Tariff.category == category,
                Tariff.unit == unit,
                Tariff.active.is_(True),
                Tariff.effective_from <= at,
                or_(Tariff.effective_to.is_(None), Tariff.effective_to > at),
            )
            .order_by(Tariff.effective_from.desc(), Tariff.id.desc())
            .limit(1)
        )
        return self.session.scalars(stmt).first()
