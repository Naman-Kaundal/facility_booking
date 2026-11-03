"""The database itself enforces the data rules, not just the Python code."""

from datetime import UTC, datetime

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import Base, Facility, FacilitySlotType, Tariff


def test_migrations_match_models(engine):
    """Fails if someone changes app/db/models.py without writing a migration (or vice versa)."""
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    # Alembic doesn't model exclusion constraints, so it sees their backing index as "extra".
    diff = [d for d in diff if not (d[0] == "remove_index" and d[1].name.startswith("ex_"))]
    assert diff == []


def _tariff(facility_id: int, **overrides) -> Tariff:
    values = {
        "facility_id": facility_id,
        "category": "PRIVATE",
        "unit": "FULL_DAY",
        "amount": 1000,
        "display_label": "x",
        "version": "constraint-test",
        "effective_from": datetime(2026, 1, 1, tzinfo=UTC),
    }
    return Tariff(**{**values, **overrides})


def _facility_id(db, code: str) -> int:
    return db.scalar(select(Facility.id).where(Facility.code == code))


def test_facility_code_is_unique(seeded_db):
    seeded_db.add(Facility(code="M5", name="Duplicate", facility_group="LHC", section="ACADEMIC"))
    with pytest.raises(IntegrityError, match="uq_facilities_code"):
        seeded_db.commit()


def test_tariff_needs_an_existing_facility(seeded_db):
    seeded_db.add(_tariff(facility_id=999_999))
    with pytest.raises(IntegrityError):
        seeded_db.commit()


def test_tariff_unit_must_be_supported_by_the_facility(seeded_db):
    # Classrooms are full-day only, so a half-day tariff for M5 is rejected by the composite foreign key.
    seeded_db.add(_tariff(_facility_id(seeded_db, "M5"), unit="HALF_DAY"))
    with pytest.raises(IntegrityError, match="fk_tariffs_facility_unit"):
        seeded_db.commit()


@pytest.mark.parametrize(
    ("overrides", "constraint"),
    [
        ({"amount": -1}, "ck_tariffs_amount_non_negative"),
        ({"category": "VIP"}, "ck_tariffs_category_valid"),
        ({"effective_to": datetime(2025, 1, 1, tzinfo=UTC)}, "ck_tariffs_effective_range"),
    ],
)
def test_tariff_check_constraints(seeded_db, overrides, constraint):
    seeded_db.add(_tariff(_facility_id(seeded_db, "M5"), **overrides))
    with pytest.raises(IntegrityError, match=constraint):
        seeded_db.commit()


def test_invalid_facility_group_is_rejected(db):
    db.add(Facility(code="X1", name="Bad", facility_group="CANTEEN", section="ACADEMIC"))
    with pytest.raises(IntegrityError, match="ck_facilities_group_valid"):
        db.commit()


def test_deleting_a_facility_removes_its_slot_types(db):
    facility = Facility(code="TMP", name="Temporary", facility_group="LHC", section="ACADEMIC")
    facility.slot_types = [FacilitySlotType(slot_type="FULL_DAY")]
    db.add(facility)
    db.commit()

    db.delete(facility)
    db.commit()
    assert db.scalar(select(FacilitySlotType).where(FacilitySlotType.facility_id == facility.id)) is None
