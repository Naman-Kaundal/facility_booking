"""Estate electricity estimate, costing and the Facilities advance intimation (LLD §8, §9, §17.3-17.4)."""

import pytest
from sqlalchemy import select

from app.db.models import Facility
from tests.helpers import decide, enter_electricity, forwarded, set_payment_url, with_estate


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


@pytest.fixture
async def people(sign_in):
    return {
        "requester": await sign_in("events@company.com", name="Asha Rao"),
        "facility": await sign_in("facilities@iitrpr.ac.in", name="Facilities Desk", roles=("FACILITY",)),
        "academic": await sign_in("academic@iitrpr.ac.in", name="Academic Desk", roles=("ACADEMIC",)),
        "sports": await sign_in("sports@iitrpr.ac.in", name="Sports Desk", roles=("SPORTS",)),
        "estate": await sign_in("estate@iitrpr.ac.in", name="Estate Desk", roles=("ESTATE",)),
        "admin": await sign_in("admin@iitrpr.ac.in", name="Admin", roles=("ADMIN",)),
    }


# PRIVATE rates: M5 full day ₹15,000; Football 3 hours ₹3,000.
MIXED = (("M5", 10, "FULL_DAY"), ("FOOTBALL", 11, "15:00-18:00"))


async def test_estate_queue_and_costing(people, facility_ids):
    request = await with_estate(people, facility_ids, *MIXED)

    queue = (await people["estate"].get("/api/v1/workflow/queue", params={"desk": "ESTATE"})).json()["items"]
    assert [i["id"] for i in queue] == [request["id"]]
    view = (await people["estate"].get(f"/api/v1/workflow/requests/{request['id']}")).json()
    assert view["can_enter_electricity"] is True and view["request"]["costs"] is None

    response = await enter_electricity(people["estate"], request["id"], 2500, "AC for 8 hours")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["request"]["status"] == "COSTED"
    costs = body["request"]["costs"]
    assert costs["booking_subtotal"] == 18000
    assert (costs["gst_amount"], costs["cleaning_amount"], costs["security_deposit"]) == (3240, 1800, 5000)
    assert (costs["electricity_estimate"], costs["electricity_advance"]) == (2500, 2000)
    assert (costs["total_estimated_cost"], costs["advance_amount"]) == (30540, 30040)
    assert costs["calculated_by_name"] == "Estate Desk"
    assert costs["payment_url"] is None and costs["is_final"] is False
    assert [i["amount"] for i in costs["items"]] == [15000, 3000]

    # It leaves the Estate queue and waits on the Facilities desk for the intimation.
    assert (await people["estate"].get("/api/v1/workflow/queue", params={"desk": "ESTATE"})).json()["items"] == []
    facility_q = (await people["facility"].get("/api/v1/workflow/queue", params={"desk": "FACILITY"})).json()
    assert [(i["id"], i["status"]) for i in facility_q["items"]] == [(request["id"], "COSTED")]


async def test_rejected_lines_are_not_charged(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, *MIXED)
    m5 = next(line["id"] for line in request["lines"] if line["facility_code"] == "M5")
    football = next(line["id"] for line in request["lines"] if line["facility_code"] == "FOOTBALL")
    await decide(people["academic"], request["id"], m5, "REJECTED", "Exams")
    await decide(people["sports"], request["id"], football, "CONFIRMED")

    costs = (await enter_electricity(people["estate"], request["id"], 0)).json()["request"]["costs"]
    assert costs["booking_subtotal"] == 3000  # only the confirmed Football line
    assert [i["facility_name"] for i in costs["items"]] == ["Football Ground"]


async def test_estate_cannot_act_before_every_section_has_decided(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, *MIXED)
    response = await enter_electricity(people["estate"], request["id"], 1000)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


async def test_only_estate_enters_electricity(people, facility_ids):
    request = await with_estate(people, facility_ids, *MIXED)
    for who in ("requester", "facility", "academic", "admin"):
        response = await enter_electricity(people[who], request["id"], 1000)
        assert response.status_code == 403, who


@pytest.mark.parametrize(
    "body",
    [
        {"electricity_estimate": -1},
        {"electricity_estimate": "lots"},
        # The browser can't send its own costs: every amount is calculated by the server.
        {"electricity_estimate": 100, "advance_amount": 1},
        {"electricity_estimate": 100, "gst_pct": 0},
    ],
)
async def test_electricity_input_is_validated(people, facility_ids, body):
    request = await with_estate(people, facility_ids, ("M5", 10, "FULL_DAY"))
    response = await people["estate"].post(f"/api/v1/requests/{request['id']}/electricity", json=body)
    assert response.status_code == 422


async def test_estate_can_revise_before_intimation(people, facility_ids):
    request = await with_estate(people, facility_ids, ("M5", 10, "FULL_DAY"))
    await enter_electricity(people["estate"], request["id"], 1000)
    response = await enter_electricity(people["estate"], request["id"], 2000, "Revised: two days of setup")
    costs = response.json()["request"]["costs"]
    assert costs["electricity_estimate"] == 2000 and costs["estimate_remark"] == "Revised: two days of setup"
    types = [e["event_type"] for e in response.json()["timeline"]]
    assert "ELECTRICITY_REVISED" in types and "COST_RECALCULATED" in types


async def test_advance_intimation(people, facility_ids):
    request = await with_estate(people, facility_ids, *MIXED)
    await enter_electricity(people["estate"], request["id"], 2500)
    url = f"/api/v1/requests/{request['id']}/intimate"

    # The requester doesn't see costs until Facilities has reviewed and sent them.
    mine = (await people["requester"].get(f"/api/v1/requests/{request['id']}")).json()
    assert mine["status"] == "COSTED" and mine["costs"] is None

    # No payment link configured yet: Facilities can't send.
    view = (await people["facility"].get(f"/api/v1/workflow/requests/{request['id']}")).json()
    assert view["payment_url_configured"] is False and view["can_intimate"] is False
    response = await people["facility"].post(url, json={})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PAYMENT_URL_NOT_CONFIGURED"

    await set_payment_url(people["admin"])
    assert (await people["estate"].post(url, json={})).status_code == 403  # only Facilities sends it
    response = await people["facility"].post(url, json={"remark": "Pay within 7 days"})
    assert response.status_code == 200, response.text
    assert response.json()["request"]["status"] == "ADVANCE_INTIMATED"

    mine = (await people["requester"].get(f"/api/v1/requests/{request['id']}")).json()
    assert mine["status"] == "ADVANCE_INTIMATED"
    assert mine["costs"]["advance_amount"] == 30040
    assert mine["costs"]["payment_url"] == "https://payments.example.org/test-only"
    assert mine["costs"]["is_final"] is True and mine["charges_preview"]["is_final"] is True

    # Sending twice is refused.
    assert (await people["facility"].post(url, json={})).status_code == 409


async def test_facilities_cannot_intimate_before_costing(people, facility_ids):
    request = await with_estate(people, facility_ids, ("M5", 10, "FULL_DAY"))
    await set_payment_url(people["admin"])
    response = await people["facility"].post(f"/api/v1/requests/{request['id']}/intimate", json={})
    assert response.status_code == 409


async def test_costed_request_keeps_its_numbers_when_settings_change(people, facility_ids):
    request = await with_estate(people, facility_ids, ("M5", 10, "FULL_DAY"))
    await enter_electricity(people["estate"], request["id"], 1000)
    response = await people["admin"].patch("/api/v1/admin/settings", json={"gst_pct": 5, "security_deposit": 0})
    assert response.status_code == 200
    costs = (await people["facility"].get(f"/api/v1/workflow/requests/{request['id']}")).json()["request"]["costs"]
    assert (costs["gst_pct"], costs["gst_amount"], costs["security_deposit"]) == (18, 2700, 5000)


async def test_timeline_records_estate_and_intimation(people, facility_ids):
    request = await with_estate(people, facility_ids, ("M5", 10, "FULL_DAY"))
    await enter_electricity(people["estate"], request["id"], 1000)
    await set_payment_url(people["admin"])
    await people["facility"].post(f"/api/v1/requests/{request['id']}/intimate", json={})
    events = (await people["requester"].get(f"/api/v1/requests/{request['id']}/events")).json()
    types = [e["event_type"] for e in events]
    assert types[-3:] == ["ELECTRICITY_SUBMITTED", "COST_CALCULATED", "ADVANCE_INTIMATED"]
    assert events[-1]["actor_name"] == "Facilities Desk"
