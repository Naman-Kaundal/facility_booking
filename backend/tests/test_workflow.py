"""Facilities review, routing to Academic/Sports, per-line decisions and status changes (LLD §8, §17.3)."""

import pytest
from sqlalchemy import select

from app.db.models import Facility
from tests.helpers import ACCEPT, decide, forwarded, line_id, submitted


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
    }


async def queue(staff, desk: str) -> list[dict]:
    response = await staff.get("/api/v1/workflow/queue", params={"desk": desk})
    assert response.status_code == 200, response.text
    return response.json()["items"]


MIXED = (("M5", 10, "FULL_DAY"), ("FOOTBALL", 11, "15:00-18:00"))


async def test_mixed_request_end_to_end(people, facility_ids):
    """Week 3 demo: submit -> Facilities forwards -> Academic and Sports decide in parallel -> Estate."""
    request = await submitted(people["requester"], facility_ids, *MIXED)

    # Facilities sees it; the sections don't yet.
    assert [i["ref_no"] for i in await queue(people["facility"], "FACILITY")] == [request["ref_no"]]
    assert await queue(people["academic"], "ACADEMIC") == []

    response = await people["facility"].post(f"/api/v1/requests/{request['id']}/forward", json={})
    assert response.status_code == 200
    assert response.json()["request"]["status"] == "WITH_SECTION"
    assert await queue(people["facility"], "FACILITY") == []

    # Each section sees the request, with only its own line pending.
    academic_q = await queue(people["academic"], "ACADEMIC")
    sports_q = await queue(people["sports"], "SPORTS")
    assert [(i["id"], i["pending_lines"]) for i in academic_q] == [(request["id"], 1)]
    assert [(i["id"], i["pending_lines"]) for i in sports_q] == [(request["id"], 1)]
    academic_view = (await people["academic"].get(f"/api/v1/workflow/requests/{request['id']}")).json()
    assert academic_view["decidable_line_ids"] == [line_id(request, "M5")]

    response = await decide(people["academic"], request["id"], line_id(request, "M5"), "CONFIRMED", "Slot is free")
    assert response.json()["request"]["status"] == "WITH_SECTION"  # Sports still to decide
    response = await decide(people["sports"], request["id"], line_id(request, "FOOTBALL"), "CONFIRMED")
    body = response.json()
    assert body["request"]["status"] == "WITH_ESTATE"
    assert {line["decision"] for line in body["request"]["lines"]} == {"CONFIRMED"}

    # The requester sees the outcome and who decided.
    mine = (await people["requester"].get(f"/api/v1/requests/{request['id']}")).json()
    m5 = next(line for line in mine["lines"] if line["facility_code"] == "M5")
    assert m5["decision"] == "CONFIRMED"
    assert (m5["decision_remark"], m5["decided_by_name"]) == ("Slot is free", "Academic Desk")

    # Every step is on the timeline, in order, with actors.
    events = (await people["requester"].get(f"/api/v1/requests/{request['id']}/events")).json()
    assert [(e["event_type"], e["actor_name"]) for e in events] == [
        ("SUBMITTED", "Asha Rao"),
        ("FORWARDED", "Facilities Desk"),
        ("LINE_CONFIRMED", "Academic Desk"),
        ("LINE_CONFIRMED", "Sports Desk"),
        ("STATUS_CHANGED", "System"),
    ]
    assert events[-1]["to_status"] == "WITH_ESTATE"
    assert events[2]["line"].startswith("LHC Classroom M5")


async def test_sports_only_request_never_reaches_academic(people, facility_ids):
    await forwarded(people["requester"], people["facility"], facility_ids, ("CRICKET", 5, "PER_DAY"))
    assert await queue(people["academic"], "ACADEMIC") == []
    assert len(await queue(people["sports"], "SPORTS")) == 1


async def test_academic_only_request_never_reaches_sports(people, facility_ids):
    await forwarded(people["requester"], people["facility"], facility_ids, ("AUDI_COMPLETE", 5, "FIRST_HALF"))
    assert await queue(people["sports"], "SPORTS") == []
    assert len(await queue(people["academic"], "ACADEMIC")) == 1


async def test_return_for_correction_and_resubmit(people, facility_ids):
    request = await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    missing_reason = await people["facility"].post(f"/api/v1/requests/{request['id']}/return", json={"reason": " "})
    assert missing_reason.status_code == 422

    response = await people["facility"].post(
        f"/api/v1/requests/{request['id']}/return", json={"reason": "Please add the organisation's full address."}
    )
    assert response.json()["request"]["status"] == "RETURNED"

    # The requester sees the reason and can edit again.
    mine = (await people["requester"].get(f"/api/v1/requests/{request['id']}")).json()
    assert mine["editable"] is True
    assert mine["return_reason"] == "Please add the organisation's full address."
    edit = await people["requester"].patch(
        f"/api/v1/requests/{request['id']}", json={"organisation_name_address": "NZES, Sector 17, Chandigarh"}
    )
    assert edit.status_code == 200

    resubmit = await people["requester"].post(f"/api/v1/requests/{request['id']}/submit", json=ACCEPT)
    assert resubmit.status_code == 200
    assert resubmit.json()["status"] == "SUBMITTED"
    assert resubmit.json()["ref_no"] == request["ref_no"]  # keeps its reference number
    events = (await people["requester"].get(f"/api/v1/requests/{request['id']}/events")).json()
    assert [e["event_type"] for e in events] == ["SUBMITTED", "RETURNED", "RESUBMITTED"]


async def test_rejection_needs_a_reason(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, ("M5", 10, "FULL_DAY"))
    response = await decide(people["academic"], request["id"], line_id(request, "M5"), "REJECTED", "   ")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REMARK_REQUIRED"


async def test_partial_rejection_continues_with_confirmed_lines(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, *MIXED)
    await decide(people["academic"], request["id"], line_id(request, "M5"), "REJECTED", "Exams that week")
    response = await decide(people["sports"], request["id"], line_id(request, "FOOTBALL"), "CONFIRMED")
    body = response.json()["request"]
    assert body["status"] == "WITH_ESTATE"
    # The rejected classroom is no longer counted in the charges.
    assert body["charges_preview"]["booking_subtotal"] == 3000


async def test_all_lines_rejected_rejects_the_request(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, *MIXED)
    await decide(people["academic"], request["id"], line_id(request, "M5"), "REJECTED", "Exams")
    response = await decide(people["sports"], request["id"], line_id(request, "FOOTBALL"), "REJECTED", "Turf repair")
    assert response.json()["request"]["status"] == "REJECTED"


async def test_a_line_cannot_be_decided_twice(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, *MIXED)
    first = await decide(people["academic"], request["id"], line_id(request, "M5"), "CONFIRMED")
    assert first.status_code == 200
    again = await decide(people["academic"], request["id"], line_id(request, "M5"), "REJECTED", "changed mind")
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "LINE_ALREADY_DECIDED"


async def test_sections_cannot_decide_before_facilities_forwards(people, facility_ids):
    request = await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    response = await decide(people["academic"], request["id"], line_id(request, "M5"), "CONFIRMED")
    # Not forwarded yet, so the Academic desk can't even see it.
    assert response.status_code in (404, 409)


async def test_stale_facilities_actions_are_refused(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, ("M5", 10, "FULL_DAY"))
    again = await people["facility"].post(f"/api/v1/requests/{request['id']}/forward", json={})
    assert again.status_code == 409
    late_return = await people["facility"].post(f"/api/v1/requests/{request['id']}/return", json={"reason": "x"})
    assert late_return.status_code == 409


async def test_drafts_are_invisible_to_staff(people, facility_ids):
    response = await people["requester"].post(
        "/api/v1/requests",
        json={
            "organisation_name_address": "Org", "applicant_name": "A", "office_contact": "0172-2345678",
            "mobile": "9876543210", "purpose": "P", "participants": 5,
        },
    )
    draft_id = response.json()["id"]
    assert (await people["facility"].get(f"/api/v1/workflow/requests/{draft_id}")).status_code == 404
    assert (await people["facility"].post(f"/api/v1/requests/{draft_id}/forward", json={})).status_code == 404
