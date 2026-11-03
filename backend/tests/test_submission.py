"""Submitting requests: terms, re-validation, reference numbers, snapshots, audit events."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core.time import today_ist
from app.db.models import BookingRequest, Facility, RequestLine, Tariff, User
from tests.helpers import ACCEPT, day, draft_with, submitted


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


async def test_terms_are_served(client):
    body = (await client.get("/api/v1/requests/terms")).json()
    assert body["version"] == ACCEPT["terms_version"]
    assert body["is_placeholder"] is True
    assert "PLACEHOLDER" in body["text"]


async def test_submit_assigns_reference_and_freezes_rates(sign_in, facility_ids):
    me = await sign_in("events@company.com", category="PRIVATE")
    body = await submitted(me, facility_ids, ("M5", 10, "FULL_DAY"), ("FOOTBALL", 11, "15:00-18:00"))

    assert body["status"] == "SUBMITTED"
    assert body["ref_no"] == f"FB-{today_ist().year}-001"
    assert body["editable"] is False
    assert body["submitted_at"] is not None
    assert body["rate_category_snapshot"] == "PRIVATE"
    assert body["terms_version"] == ACCEPT["terms_version"]
    lines = {line["facility_code"]: line for line in body["lines"]}
    assert lines["M5"]["rate"]["amount"] == 15000
    assert lines["M5"]["section"] == "ACADEMIC"
    assert lines["FOOTBALL"]["section"] == "SPORTS"
    assert {line["decision"] for line in body["lines"]} == {"PENDING"}
    assert body["charges_preview"]["booking_subtotal"] == 18000


async def test_reference_numbers_count_up(sign_in, facility_ids):
    alice = await sign_in("alice@company.com")
    bob = await sign_in("bob@company.com")
    first = await submitted(alice, facility_ids, ("M3", 5, "FULL_DAY"))
    second = await submitted(bob, facility_ids, ("M4", 5, "FULL_DAY"))
    year = today_ist().year
    assert (first["ref_no"], second["ref_no"]) == (f"FB-{year}-001", f"FB-{year}-002")


async def test_snapshot_survives_tariff_and_category_changes(sign_in, facility_ids, seeded_db):
    me = await sign_in("events@company.com", category="PRIVATE")
    body = await submitted(me, facility_ids, ("M5", 10, "FULL_DAY"))

    seeded_db.execute(update(Tariff).where(Tariff.facility_id == facility_ids["M5"]).values(amount=99999))
    seeded_db.execute(update(User).where(User.email == "events@company.com").values(rate_category="GOVT"))
    seeded_db.commit()

    again = (await me.get(f"/api/v1/requests/{body['id']}")).json()
    assert again["lines"][0]["rate"]["amount"] == 15000
    assert again["rate_category_snapshot"] == "PRIVATE"
    stored = seeded_db.scalar(select(RequestLine.line_amount_snapshot).where(RequestLine.request_id == body["id"]))
    assert stored == 15000


async def test_terms_must_be_accepted(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await draft_with(me, facility_ids, ("M5", 10, "FULL_DAY"))
    response = await me.post(f"/api/v1/requests/{draft['id']}/submit", json={**ACCEPT, "terms_accepted": False})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "TERMS_REQUIRED"


async def test_outdated_terms_version_is_rejected(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await draft_with(me, facility_ids, ("M5", 10, "FULL_DAY"))
    response = await me.post(f"/api/v1/requests/{draft['id']}/submit", json={**ACCEPT, "terms_version": "v0"})
    assert response.json()["error"]["code"] == "TERMS_OUTDATED"


async def test_request_without_facilities_cannot_be_submitted(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await draft_with(me, facility_ids)
    response = await me.post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "NO_LINES"


async def test_cannot_submit_twice(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    body = await submitted(me, facility_ids, ("M5", 10, "FULL_DAY"))
    response = await me.post(f"/api/v1/requests/{body['id']}/submit", json=ACCEPT)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "INVALID_STATE"


async def test_submitted_request_cannot_be_edited(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    body = await submitted(me, facility_ids, ("M5", 10, "FULL_DAY"))
    response = await me.patch(f"/api/v1/requests/{body['id']}", json={"purpose": "changed"})
    assert response.status_code == 409


async def test_lines_are_revalidated_at_submission(sign_in, facility_ids, seeded_db):
    me = await sign_in("events@company.com")
    draft = await draft_with(me, facility_ids, ("M5", 10, "FULL_DAY"))
    # Simulate a draft left open until its date passed.
    yesterday = today_ist() - timedelta(days=1)
    seeded_db.execute(update(RequestLine).where(RequestLine.request_id == draft["id"]).values(booking_date=yesterday))
    seeded_db.commit()
    response = await me.post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)
    assert response.json()["error"]["code"] == "DATE_IN_PAST"


async def test_other_users_cannot_submit_my_draft(sign_in, facility_ids):
    alice = await sign_in("alice@company.com")
    bob = await sign_in("bob@company.com")
    draft = await draft_with(alice, facility_ids, ("M5", 10, "FULL_DAY"))
    response = await bob.post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)
    assert response.status_code == 404


async def test_submission_is_recorded_in_the_timeline(sign_in, facility_ids):
    me = await sign_in("events@company.com", name="Asha Rao")
    body = await submitted(me, facility_ids, ("M5", 10, "FULL_DAY"))
    events = (await me.get(f"/api/v1/requests/{body['id']}/events")).json()
    assert [(e["event_type"], e["from_status"], e["to_status"], e["actor_name"]) for e in events] == [
        ("SUBMITTED", "DRAFT", "SUBMITTED", "Asha Rao")
    ]


async def test_timeline_is_private(sign_in, facility_ids):
    alice = await sign_in("alice@company.com")
    bob = await sign_in("bob@company.com")
    body = await submitted(alice, facility_ids, ("M5", 10, "FULL_DAY"))
    assert (await bob.get(f"/api/v1/requests/{body['id']}/events")).status_code == 404


async def test_my_requests_shows_reference_and_status(sign_in, facility_ids, seeded_db):
    me = await sign_in("events@company.com")
    body = await submitted(me, facility_ids, ("M5", 10, "FULL_DAY"))
    item = (await me.get("/api/v1/requests")).json()["items"][0]
    assert (item["ref_no"], item["status"]) == (body["ref_no"], "SUBMITTED")
    assert seeded_db.scalar(select(BookingRequest.status).where(BookingRequest.id == body["id"])) == "SUBMITTED"


def test_day_helper_is_in_the_future():
    assert day(1) > today_ist().isoformat()
