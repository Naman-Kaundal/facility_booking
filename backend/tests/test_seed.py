from sqlalchemy import func, select, update

from app.db.models import Facility, FacilitySlotType, SlotWindow, Tariff
from app.db.seed import seed_all
from app.db.seed_data import FACILITIES, TARIFFS

EXPECTED = {
    "facilities": len(FACILITIES),  # 10
    "facility_slot_types": 11,  # every facility has one, the Auditorium complete space has two
    "tariffs": sum(len(amounts) for amounts in TARIFFS.values()),  # 11 facility/unit rows x 3 categories = 33
    "slot_windows": 16,
}
MODELS = {
    "facilities": Facility,
    "facility_slot_types": FacilitySlotType,
    "tariffs": Tariff,
    "slot_windows": SlotWindow,
}


def _counts(db) -> dict[str, int]:
    return {name: db.scalar(select(func.count()).select_from(model)) for name, model in MODELS.items()}


def test_first_seed_inserts_everything(db):
    report = seed_all(db)
    assert report.inserted == EXPECTED
    assert set(report.existing.values()) == {0}
    assert _counts(db) == EXPECTED
    assert EXPECTED["tariffs"] == 33


def test_seed_is_idempotent(db):
    seed_all(db)
    report = seed_all(db)
    assert _counts(db) == EXPECTED
    assert set(report.inserted.values()) == {0}
    assert report.existing == EXPECTED


def test_rerunning_seed_does_not_overwrite_admin_changes(db):
    seed_all(db)
    m5_id = db.scalar(select(Facility.id).where(Facility.code == "M5"))
    db.execute(
        update(Tariff)
        .where(Tariff.facility_id == m5_id, Tariff.category == "PRIVATE", Tariff.unit == "FULL_DAY")
        .values(amount=16000)
    )
    db.commit()

    seed_all(db)

    amount = db.scalar(
        select(Tariff.amount).where(
            Tariff.facility_id == m5_id, Tariff.category == "PRIVATE", Tariff.unit == "FULL_DAY"
        )
    )
    assert amount == 16000


def test_no_charge_tariffs_are_stored_as_zero(db):
    seed_all(db)
    assert db.scalar(select(func.count()).select_from(Tariff).where(Tariff.amount == 0)) == 3
