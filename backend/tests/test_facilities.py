from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update

from app.db.models import Facility, Tariff
from app.db.seed_data import FACILITIES


async def test_catalogue_returns_all_seeded_facilities_in_order(client):
    response = await client.get("/api/v1/facilities")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == len(FACILITIES) == 10
    assert [f["code"] for f in body["items"]] == [f["code"] for f in FACILITIES]


async def test_catalogue_item_shape(client):
    items = {f["code"]: f for f in (await client.get("/api/v1/facilities")).json()["items"]}
    m5 = items["M5"]
    assert m5["name"] == "LHC Classroom M5"
    assert m5["group"] == "LHC"
    assert m5["section"] == "ACADEMIC"
    assert m5["capacity"] == 150
    assert m5["slot_types"] == ["FULL_DAY"]
    assert m5["id"].isdigit()
    assert {(t["category"], t["amount"]) for t in m5["tariffs"]} == {
        ("PRIVATE", 15000),
        ("GOVT", 10000),
        ("IIT", 7000),
    }


async def test_sports_facilities_route_to_sports_with_free_iit_rate(client):
    items = {f["code"]: f for f in (await client.get("/api/v1/facilities")).json()["items"]}
    for code in ("CRICKET", "FOOTBALL", "HOCKEY"):
        assert items[code]["section"] == "SPORTS"
        iit = next(t for t in items[code]["tariffs"] if t["category"] == "IIT")
        assert iit["amount"] == 0
        assert iit["display_label"] == "No charges"
    football_slots = items["FOOTBALL"]["slot_options"]
    assert [s["slot_key"] for s in football_slots] == ["09:00-12:00", "12:00-15:00", "15:00-18:00"]
    assert (football_slots[0]["start"], football_slots[0]["end"]) == ("09:00", "12:00")


async def test_only_auditorium_complete_offers_half_day(client):
    items = (await client.get("/api/v1/facilities")).json()["items"]
    half_day = [f["code"] for f in items if "HALF_DAY" in f["slot_types"]]
    assert half_day == ["AUDI_COMPLETE"]
    audi = next(f for f in items if f["code"] == "AUDI_COMPLETE")
    assert audi["slot_types"] == ["FULL_DAY", "HALF_DAY"]
    half_tariffs = {t["category"]: t["amount"] for t in audi["tariffs"] if t["unit"] == "HALF_DAY"}
    assert half_tariffs == {"PRIVATE": 30000, "GOVT": 20000, "IIT": 15000}
    assert [s["slot_key"] for s in audi["slot_options"]] == ["FULL_DAY", "FIRST_HALF", "SECOND_HALF"]


async def test_inactive_facilities_are_hidden_by_default(client, seeded_db):
    seeded_db.execute(update(Facility).where(Facility.code == "HOCKEY").values(active=False))
    seeded_db.commit()
    active_codes = [f["code"] for f in (await client.get("/api/v1/facilities")).json()["items"]]
    assert "HOCKEY" not in active_codes
    inactive = (await client.get("/api/v1/facilities", params={"active": "false"})).json()["items"]
    assert [f["code"] for f in inactive] == ["HOCKEY"]


async def test_newer_effective_tariff_replaces_older_one(client, seeded_db):
    m3_id = seeded_db.scalar(select(Facility.id).where(Facility.code == "M3"))
    now = datetime.now(UTC)
    common = {"facility_id": m3_id, "category": "PRIVATE", "unit": "FULL_DAY", "effective_to": None}
    seeded_db.add_all(
        [
            Tariff(**common, version="test-v2", amount=12000, display_label="₹12,000 / full day",
                   effective_from=now - timedelta(days=1)),
            # A future-dated tariff must not apply yet.
            Tariff(**common, version="test-future", amount=99999, display_label="future",
                   effective_from=now + timedelta(days=30)),
        ]
    )
    seeded_db.commit()

    facility = (await client.get("/api/v1/facilities/M3")).json()
    private = [t for t in facility["tariffs"] if t["category"] == "PRIVATE"]
    assert len(private) == 1
    assert private[0]["amount"] == 12000


async def test_expired_tariff_is_not_shown(client, seeded_db):
    m4_id = seeded_db.scalar(select(Facility.id).where(Facility.code == "M4"))
    seeded_db.execute(
        update(Tariff)
        .where(Tariff.facility_id == m4_id, Tariff.category == "GOVT")
        .values(effective_to=datetime.now(UTC) - timedelta(seconds=1))
    )
    seeded_db.commit()
    facility = (await client.get("/api/v1/facilities/M4")).json()
    assert {t["category"] for t in facility["tariffs"]} == {"PRIVATE", "IIT"}


async def test_get_facility_by_code_and_404(client):
    ok = await client.get("/api/v1/facilities/CRICKET")
    assert ok.status_code == 200
    assert ok.json()["slot_types"] == ["PER_DAY"]

    missing = await client.get("/api/v1/facilities/NOPE")
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {"code": "FACILITY_NOT_FOUND", "message": "No facility with code 'NOPE'.", "details": {}}
    }


async def test_invalid_query_parameter_uses_error_format(client):
    response = await client.get("/api/v1/facilities", params={"active": "maybe"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
