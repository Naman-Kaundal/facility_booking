"""Admin management (LLD §3 ADMIN, §11.5, §17.1): only admins, validated, audited, future-only."""

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.time import today_ist
from app.db.models import Facility
from tests.helpers import EVENT, day, submitted


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


@pytest.fixture
async def admin(sign_in):
    return await sign_in("admin@iitrpr.ac.in", name="Admin", roles=("ADMIN",))


ADMIN_ROUTES = [
    ("GET", "/api/v1/admin/settings", None),
    ("PATCH", "/api/v1/admin/settings", {"gst_pct": 5}),
    ("GET", "/api/v1/admin/staff-roles", None),
    ("POST", "/api/v1/admin/staff-roles", {"email": "x@gmail.com", "role": "ADMIN"}),
    ("GET", "/api/v1/admin/facilities", None),
    ("GET", "/api/v1/admin/emails", None),
    ("POST", "/api/v1/admin/emails/retry", None),
    ("GET", "/api/v1/admin/audit", None),
]


@pytest.mark.parametrize(("method", "url", "body"), ADMIN_ROUTES)
async def test_admin_endpoints_reject_non_admins(sign_in, method, url, body):
    for email, roles in (("events@company.com", ()), ("facilities@iitrpr.ac.in", ("FACILITY", "ESTATE"))):
        user = await sign_in(email, roles=roles)
        response = await user.request(method, url, json=body)
        assert response.status_code == 403, (email, response.text)


async def test_settings_update_and_validation(admin):
    current = (await admin.get("/api/v1/admin/settings")).json()
    assert current["gst_pct"] == 18 and current["payment_url"] is None

    response = await admin.patch(
        "/api/v1/admin/settings",
        json={"gst_pct": 12.5, "security_deposit": 2000, "payment_url": "https://payments.example.org/x"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (body["gst_pct"], body["security_deposit"], body["updated_by"]) == (12.5, 2000, "admin@iitrpr.ac.in")

    for bad in ({"gst_pct": 101}, {"cleaning_pct": -1}, {"security_deposit": -1},
                {"payment_url": "not a url"}, {"payment_url": "javascript:alert(1)"}, {}, {"advance_amount": 1}):
        assert (await admin.patch("/api/v1/admin/settings", json=bad)).status_code == 422, bad

    cleared = await admin.patch("/api/v1/admin/settings", json={"payment_url": ""})
    assert cleared.json()["payment_url"] is None

    audit = (await admin.get("/api/v1/admin/audit")).json()
    assert [a["action"] for a in audit][:2] == ["SETTINGS_UPDATED", "SETTINGS_UPDATED"]


async def test_staff_roles(admin, sign_in):
    response = await admin.post(
        "/api/v1/admin/staff-roles", json={"email": " New.Estate@Gmail.com ", "role": "ESTATE"}
    )
    assert response.status_code == 201
    role = response.json()
    assert (role["email"], role["role"], role["active"]) == ("new.estate@gmail.com", "ESTATE", True)

    estate = await sign_in("new.estate@gmail.com")
    assert (await estate.get("/api/v1/workflow/queue", params={"desk": "ESTATE"})).status_code == 200

    response = await admin.patch(f"/api/v1/admin/staff-roles/{role['id']}", json={"active": False})
    assert response.json()["active"] is False
    assert (await estate.get("/api/v1/workflow/queue", params={"desk": "ESTATE"})).status_code == 403

    assert (await admin.post("/api/v1/admin/staff-roles", json={"email": "a@b.com", "role": "BOSS"})).status_code == 422


async def test_admin_cannot_remove_own_admin_role(admin):
    roles = (await admin.get("/api/v1/admin/staff-roles")).json()
    mine = next(r for r in roles if r["email"] == "admin@iitrpr.ac.in" and r["role"] == "ADMIN")
    response = await admin.patch(f"/api/v1/admin/staff-roles/{mine['id']}", json={"active": False})
    assert response.status_code == 409


async def test_deactivating_a_facility_hides_it_from_booking(admin, sign_in, facility_ids):
    response = await admin.patch(f"/api/v1/admin/facilities/{facility_ids['M6']}", json={"active": False})
    assert response.status_code == 200 and response.json()["active"] is False
    catalogue = (await admin.get("/api/v1/facilities")).json()["items"]
    assert "M6" not in [f["code"] for f in catalogue]
    listed = (await admin.get("/api/v1/admin/facilities")).json()
    assert "M6" in [f["code"] for f in listed]  # admins still see it


async def test_new_tariff_applies_from_its_start_date_only(admin, sign_in, facility_ids):
    requester = await sign_in("events@company.com")
    # Submitted before the change: keeps ₹15,000.
    before = await submitted(requester, facility_ids, ("M5", 10, "FULL_DAY"))

    start = today_ist() + timedelta(days=5)
    response = await admin.post(
        "/api/v1/admin/tariffs",
        json={"facility_id": facility_ids["M5"], "category": "PRIVATE", "unit": "FULL_DAY", "amount": 18000,
              "effective_from": start.isoformat()},
    )
    assert response.status_code == 201, response.text
    m5_private = [t for t in response.json()["tariffs"] if t["category"] == "PRIVATE"]
    assert [t["amount"] for t in m5_private] == [18000, 15000]  # newest first; old one closed at `start`

    still = (await requester.get(f"/api/v1/requests/{before['id']}")).json()
    assert still["lines"][0]["rate"]["amount"] == 15000  # snapshot unchanged

    draft = (await requester.post("/api/v1/requests", json=EVENT)).json()
    lines_url = f"/api/v1/requests/{draft['id']}/lines"
    early = await requester.post(
        lines_url, json={"facility_id": facility_ids["M5"], "booking_date": day(2), "slot_key": "FULL_DAY"}
    )
    late = await requester.post(
        lines_url, json={"facility_id": facility_ids["M5"], "booking_date": day(20), "slot_key": "FULL_DAY"}
    )
    rates = {line["booking_date"]: line["rate"]["amount"] for line in late.json()["lines"]}
    assert early.status_code == 201
    assert rates == {day(2): 15000, day(20): 18000}


async def test_tariff_validation(admin, facility_ids):
    base = {"facility_id": facility_ids["M5"], "category": "PRIVATE", "unit": "FULL_DAY", "amount": 1000}
    past = await admin.post("/api/v1/admin/tariffs", json={**base, "effective_from": day(-1)})
    assert past.status_code == 422
    half = await admin.post("/api/v1/admin/tariffs", json={**base, "unit": "HALF_DAY", "effective_from": day(1)})
    assert half.status_code == 422 and half.json()["error"]["code"] == "UNIT_NOT_SUPPORTED"
    negative = await admin.post("/api/v1/admin/tariffs", json={**base, "amount": -5, "effective_from": day(1)})
    assert negative.status_code == 422
    first = await admin.post("/api/v1/admin/tariffs", json={**base, "effective_from": day(10)})
    assert first.status_code == 201
    earlier = await admin.post("/api/v1/admin/tariffs", json={**base, "effective_from": day(5)})
    assert earlier.status_code == 409  # a later rate is already scheduled


async def test_slot_window_edits(admin, facility_ids):
    facilities = (await admin.get("/api/v1/admin/facilities")).json()
    audi = next(f for f in facilities if f["code"] == "AUDI_COMPLETE")
    first_half = next(s for s in audi["slots"] if s["slot_key"] == "FIRST_HALF")
    full_day = next(s for s in audi["slots"] if s["slot_key"] == "FULL_DAY")

    slot_url = f"/api/v1/admin/slot-windows/{first_half['id']}"
    new_times = {"start": "09:30", "end": "13:30", "label": "First half (09:30–13:30)"}
    response = await admin.patch(slot_url, json=new_times)
    assert response.status_code == 200, response.text
    updated = next(s for s in response.json()["slots"] if s["id"] == first_half["id"])
    assert (updated["start"], updated["end"]) == ("09:30", "13:30")

    bad = await admin.patch(slot_url, json={"start": "14:00", "end": "13:00"})
    assert bad.status_code == 422
    whole = await admin.patch(f"/api/v1/admin/slot-windows/{full_day['id']}", json={"start": "09:00", "end": "17:00"})
    assert whole.status_code == 422

    off = await admin.patch(slot_url, json={"active": False})
    assert next(s for s in off.json()["slots"] if s["id"] == first_half["id"])["active"] is False
    catalogue = (await admin.get("/api/v1/facilities/AUDI_COMPLETE")).json()
    assert "FIRST_HALF" not in [s["slot_key"] for s in catalogue["slot_options"]]
