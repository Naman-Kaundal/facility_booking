"""Idempotent seed for facilities, their slot types, tariffs and slot windows.

Run with:  python -m app.db.seed   (after `alembic upgrade head`)

Every row is written with ``INSERT ... ON CONFLICT DO NOTHING`` on its natural key,
so rerunning the seed never creates duplicates and never overwrites values that
were changed in the database later.
"""

from dataclasses import dataclass, field
from datetime import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import Facility, FacilitySlotType, SlotWindow, Tariff
from app.db.seed_data import (
    FACILITIES,
    SEED_TARIFF_EFFECTIVE_FROM,
    SEED_TARIFF_VERSION,
    SLOT_WINDOWS_BY_TYPE,
    TARIFFS,
    tariff_display_label,
)

TABLES = ("facilities", "facility_slot_types", "tariffs", "slot_windows")


@dataclass
class SeedReport:
    inserted: dict[str, int] = field(default_factory=lambda: dict.fromkeys(TABLES, 0))
    existing: dict[str, int] = field(default_factory=lambda: dict.fromkeys(TABLES, 0))

    def count(self, table: str, was_inserted: bool) -> None:
        bucket = self.inserted if was_inserted else self.existing
        bucket[table] += 1


def _insert_if_missing(session: Session, model, values: dict, conflict_cols: list[str], report: SeedReport) -> None:
    pk_col = next(iter(model.__table__.primary_key.columns))
    stmt = insert(model).values(**values).on_conflict_do_nothing(index_elements=conflict_cols).returning(pk_col)
    inserted = session.execute(stmt).first() is not None
    report.count(model.__tablename__, inserted)


def _to_time(value: str | None) -> time | None:
    return time.fromisoformat(value) if value else None


def seed_all(session: Session) -> SeedReport:
    report = SeedReport()

    # Facilities
    for facility in FACILITIES:
        values = {
            "code": facility["code"],
            "name": facility["name"],
            "facility_group": facility["group"],
            "section": facility["section"],
            "capacity": facility.get("capacity"),
            "sort_order": facility.get("sort_order", 0),
            "notes": facility.get("notes"),
        }
        _insert_if_missing(session, Facility, values, ["code"], report)

    facility_ids = dict(session.execute(select(Facility.code, Facility.id)).all())

    # Supported slot types per facility
    for facility in FACILITIES:
        for slot_type in facility["slot_types"]:
            values = {"facility_id": facility_ids[facility["code"]], "slot_type": slot_type}
            _insert_if_missing(session, FacilitySlotType, values, ["facility_id", "slot_type"], report)

    # Tariffs
    for (code, unit), amounts in TARIFFS.items():
        for category, amount in amounts.items():
            values = {
                "facility_id": facility_ids[code],
                "category": category,
                "unit": unit,
                "version": SEED_TARIFF_VERSION,
                "amount": amount,
                "display_label": tariff_display_label(amount, unit),
                "effective_from": SEED_TARIFF_EFFECTIVE_FROM,
                "effective_to": None,
            }
            _insert_if_missing(session, Tariff, values, ["facility_id", "category", "unit", "version"], report)

    # Slot windows
    for facility in FACILITIES:
        for slot_type in facility["slot_types"]:
            for window in SLOT_WINDOWS_BY_TYPE[slot_type]:
                values = {
                    "facility_id": facility_ids[facility["code"]],
                    "slot_type": slot_type,
                    "slot_key": window["slot_key"],
                    "label": window["label"],
                    "start_time": _to_time(window["start"]),
                    "end_time": _to_time(window["end"]),
                    "half": window["half"],
                }
                _insert_if_missing(session, SlotWindow, values, ["facility_id", "slot_key"], report)

    session.commit()
    return report


def _main() -> None:
    from sqlalchemy.engine import make_url

    from app.core.config import get_settings
    from app.db.session import create_session_factory

    settings = get_settings()
    factory = create_session_factory(settings)
    with factory() as session:
        report = seed_all(session)
    factory.kw["bind"].dispose()

    print(f"Seeded database '{make_url(settings.database_url).database}'.")
    for name in TABLES:
        print(f"  {name:<20} inserted={report.inserted[name]:<3} already present={report.existing[name]}")


if __name__ == "__main__":
    _main()
