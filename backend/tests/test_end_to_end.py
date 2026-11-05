"""The full happy path from sign-in to advance intimation, through the public API only (Week 4 demo)."""

import pytest
from sqlalchemy import select

from app.db.models import Facility
from tests.helpers import ACCEPT, EVENT, day


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


async def test_sign_in_to_advance_intimation(sign_in, facility_ids, outbox):
    # Staff and admin, set up by email.
    admin = await sign_in("admin@iitrpr.ac.in", name="Admin", roles=("ADMIN",))
    facility = await sign_in("facilities@iitrpr.ac.in", name="Facilities", roles=("FACILITY",))
    academic = await sign_in("academic@iitrpr.ac.in", name="Academic", roles=("ACADEMIC",))
    sports = await sign_in("sports@iitrpr.ac.in", name="Sports", roles=("SPORTS",))
    estate = await sign_in("estate@iitrpr.ac.in", name="Estate", roles=("ESTATE",))
    await admin.patch("/api/v1/admin/settings", json={"payment_url": "https://payments.example.org/test-only"})

    # 1. An external (Govt.) requester signs in and builds a mixed request.
    requester = await sign_in("organiser@gmail.com", category="GOVT", name="R. Mehta")
    me = (await requester.get("/api/v1/users/me")).json()
    assert me["rate_category"] == "GOVT" and me["roles"] == []
    draft = (await requester.post("/api/v1/requests", json=EVENT)).json()
    for code, offset, slot in (("AUDI_COMPLETE", 14, "FIRST_HALF"), ("CRICKET", 15, "PER_DAY")):
        response = await requester.post(
            f"/api/v1/requests/{draft['id']}/lines",
            json={"facility_id": facility_ids[code], "booking_date": day(offset), "slot_key": slot},
        )
        assert response.status_code == 201, response.text

    # 2. Submit with the terms.
    request = (await requester.post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)).json()
    assert request["status"] == "SUBMITTED" and request["ref_no"].startswith("FB-")
    rid = request["id"]

    # 3. Facilities forwards; Academic and Sports decide in parallel.
    assert (await facility.post(f"/api/v1/requests/{rid}/forward", json={})).status_code == 200
    lines = {line["facility_code"]: line["id"] for line in request["lines"]}
    decision_url = f"/api/v1/requests/{rid}/decision"
    await academic.post(decision_url, json={"line_id": lines["AUDI_COMPLETE"], "decision": "CONFIRMED"})
    response = await sports.post(decision_url, json={"line_id": lines["CRICKET"], "decision": "CONFIRMED"})
    assert response.json()["request"]["status"] == "WITH_ESTATE"

    # 4. Estate enters electricity; the server costs it.
    response = await estate.post(f"/api/v1/requests/{rid}/electricity", json={"electricity_estimate": 4000})
    costs = response.json()["request"]["costs"]
    # GOVT rates: Auditorium half day ₹20,000 + Cricket ₹8,000 = ₹28,000.
    assert costs["booking_subtotal"] == 28000
    assert costs["gst_amount"] == 5040 and costs["cleaning_amount"] == 2800
    assert costs["total_estimated_cost"] == 28000 + 5040 + 2800 + 5000 + 4000
    assert costs["advance_amount"] == 28000 + 5040 + 2800 + 5000 + 3200

    # 5. Facilities sends the advance intimation.
    response = await facility.post(f"/api/v1/requests/{rid}/intimate", json={})
    assert response.json()["request"]["status"] == "ADVANCE_INTIMATED"

    # 6. The requester sees the final status, the breakdown and the payment link, and got the email.
    final = (await requester.get(f"/api/v1/requests/{rid}")).json()
    assert final["status"] == "ADVANCE_INTIMATED"
    assert final["costs"]["advance_amount"] == 44040
    assert final["costs"]["payment_url"] == "https://payments.example.org/test-only"
    assert outbox.to("organiser@gmail.com")[-1].subject.endswith("advance payment details")

    # Every step is on the timeline.
    types = [e["event_type"] for e in (await requester.get(f"/api/v1/requests/{rid}/events")).json()]
    assert types == [
        "SUBMITTED", "FORWARDED", "LINE_CONFIRMED", "LINE_CONFIRMED", "STATUS_CHANGED",
        "ELECTRICITY_SUBMITTED", "COST_CALCULATED", "ADVANCE_INTIMATED",
    ]
