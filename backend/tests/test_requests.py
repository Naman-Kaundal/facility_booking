"""Draft requests: create/edit/delete, multi-facility lines, validation, ownership, tariff preview."""

from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.core.time import today_ist
from app.db.models import BookingRequest, Facility

EVENT = {
    "organisation_name_address": "North Zone Education Society, Chandigarh",
    "applicant_name": "R. Mehta",
    "office_contact": "0172-2345678",
    "mobile": "+91 98765 43210",
    "purpose": "Annual student conference",
    "participants": 180,
}


def day(offset: int) -> str:
    return (today_ist() + timedelta(days=offset)).isoformat()


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


async def create_draft(client, **overrides) -> dict:
    response = await client.post("/api/v1/requests", json={**EVENT, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


async def add_line(client, request_id: int, facility_id: int, date: str, slot_key: str):
    return await client.post(
        f"/api/v1/requests/{request_id}/lines",
        json={"facility_id": facility_id, "booking_date": date, "slot_key": slot_key},
    )


# ----- creating and reading drafts -----


async def test_create_draft_uses_verified_email_and_starts_as_draft(sign_in):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    assert draft["status"] == "DRAFT"
    assert draft["ref_no"] is None
    assert draft["editable"] is True
    assert draft["event"]["contact_email"] == "events@company.com"
    assert draft["event"]["participants"] == 180
    assert draft["lines"] == []
    assert draft["charges_preview"]["booking_subtotal"] == 0
    assert draft["charges_preview"]["is_final"] is False


async def test_draft_with_two_facilities_on_different_dates(sign_in, facility_ids):
    """Week 2 demo: an Academic and a Sports facility, each with its own date and slot."""
    me = await sign_in("events@company.com", category="PRIVATE")
    draft = await create_draft(me)
    assert (await add_line(me, draft["id"], facility_ids["M5"], day(10), "FULL_DAY")).status_code == 201
    response = await add_line(me, draft["id"], facility_ids["FOOTBALL"], day(11), "15:00-18:00")
    assert response.status_code == 201
    body = response.json()

    lines = {line["facility_code"]: line for line in body["lines"]}
    assert lines["M5"]["section"] == "ACADEMIC"
    assert lines["M5"]["rate"]["amount"] == 15000
    assert lines["FOOTBALL"]["section"] == "SPORTS"
    assert lines["FOOTBALL"]["slot_label"] == "15:00–18:00"
    assert lines["FOOTBALL"]["rate"]["amount"] == 3000
    assert body["charges_preview"] == {
        "category": "PRIVATE",
        "booking_subtotal": 18000,
        "lines_without_rate": 0,
        "is_final": False,
        "note": body["charges_preview"]["note"],
    }

    # Persisted: reading it again returns the same lines.
    again = (await me.get(f"/api/v1/requests/{draft['id']}")).json()
    assert [line["id"] for line in again["lines"]] == [line["id"] for line in body["lines"]]


@pytest.mark.parametrize(
    ("email", "category", "m5", "cricket"),
    [
        ("asha@iitrpr.ac.in", None, 7000, 0),  # IIT rate, sports grounds free
        ("officer@gov.in", "GOVT", 10000, 8000),
        ("events@company.com", "PRIVATE", 15000, 10000),
    ],
)
async def test_tariff_preview_follows_the_users_category(sign_in, facility_ids, email, category, m5, cricket):
    me = await sign_in(email, category=category)
    draft = await create_draft(me)
    await add_line(me, draft["id"], facility_ids["M5"], day(5), "FULL_DAY")
    body = (await add_line(me, draft["id"], facility_ids["CRICKET"], day(6), "PER_DAY")).json()
    amounts = {line["facility_code"]: line["rate"]["amount"] for line in body["lines"]}
    assert amounts == {"M5": m5, "CRICKET": cricket}
    assert body["charges_preview"]["booking_subtotal"] == m5 + cricket


async def test_my_requests_lists_only_my_requests(sign_in, facility_ids):
    alice = await sign_in("alice@company.com")
    bob = await sign_in("bob@company.com")
    a1 = await create_draft(alice, purpose="Alice event")
    await add_line(alice, a1["id"], facility_ids["M5"], day(3), "FULL_DAY")
    await add_line(alice, a1["id"], facility_ids["HOCKEY"], day(3), "09:00-12:00")
    await create_draft(bob, purpose="Bob event")

    listing = (await alice.get("/api/v1/requests")).json()
    assert listing["total"] == 1
    item = listing["items"][0]
    assert item["purpose"] == "Alice event"
    assert item["line_count"] == 2
    assert item["facility_summary"] == "LHC Classroom M5, Hockey Ground"
    assert item["first_date"] == day(3)


async def test_other_users_request_is_not_found(sign_in):
    alice = await sign_in("alice@company.com")
    bob = await sign_in("bob@company.com")
    draft = await create_draft(alice)
    for response in (
        await bob.get(f"/api/v1/requests/{draft['id']}"),
        await bob.patch(f"/api/v1/requests/{draft['id']}", json={"purpose": "hijack"}),
        await bob.delete(f"/api/v1/requests/{draft['id']}"),
        await bob.post(
            f"/api/v1/requests/{draft['id']}/lines", json={"facility_id": 1, "booking_date": day(2), "slot_key": "x"}
        ),
    ):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "REQUEST_NOT_FOUND"
    assert (await alice.get(f"/api/v1/requests/{draft['id']}")).json()["event"]["purpose"] == EVENT["purpose"]


# ----- validation -----


@pytest.mark.parametrize(
    "overrides",
    [
        {"applicant_name": "   "},
        {"purpose": ""},
        {"participants": 0},
        {"participants": -5},
        {"participants": 2.5},
        {"mobile": "call me"},
        {"office_contact": "12"},
    ],
)
async def test_invalid_event_details_are_rejected(sign_in, overrides):
    me = await sign_in("events@company.com")
    response = await me.post("/api/v1/requests", json={**EVENT, **overrides})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_missing_required_field_is_rejected(sign_in):
    me = await sign_in("events@company.com")
    event = {k: v for k, v in EVENT.items() if k != "organisation_name_address"}
    assert (await me.post("/api/v1/requests", json=event)).status_code == 422


@pytest.mark.parametrize("field", ["user_id", "rate_category", "status", "contact_email", "ref_no"])
async def test_server_decided_fields_cannot_be_sent(sign_in, field):
    me = await sign_in("events@company.com")
    response = await me.post("/api/v1/requests", json={**EVENT, field: "IIT"})
    assert response.status_code == 422


async def test_external_user_must_choose_category_first(sign_in):
    me = await sign_in("someone@gmail.com", category=None)
    response = await me.post("/api/v1/requests", json=EVENT)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PROFILE_INCOMPLETE"


async def test_classroom_has_no_half_day_slot(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    response = await add_line(me, draft["id"], facility_ids["M5"], day(4), "FIRST_HALF")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_SLOT"


async def test_unknown_facility_is_rejected(sign_in):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    response = await add_line(me, draft["id"], 999_999, day(4), "FULL_DAY")
    assert response.json()["error"]["code"] == "INVALID_FACILITY"


async def test_inactive_facility_is_rejected(sign_in, facility_ids, seeded_db):
    seeded_db.execute(update(Facility).where(Facility.code == "HOCKEY").values(active=False))
    seeded_db.commit()
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    response = await add_line(me, draft["id"], facility_ids["HOCKEY"], day(4), "09:00-12:00")
    assert response.json()["error"]["code"] == "INVALID_FACILITY"


async def test_past_date_is_rejected(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    response = await add_line(me, draft["id"], facility_ids["M5"], day(-1), "FULL_DAY")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "DATE_IN_PAST"


async def test_today_is_allowed_but_more_than_a_year_ahead_is_not(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    assert (await add_line(me, draft["id"], facility_ids["M5"], day(0), "FULL_DAY")).status_code == 201
    response = await add_line(me, draft["id"], facility_ids["M6"], day(400), "FULL_DAY")
    assert response.json()["error"]["code"] == "DATE_TOO_FAR"


async def test_overlapping_lines_in_one_request_are_rejected(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    audi = facility_ids["AUDI_COMPLETE"]
    assert (await add_line(me, draft["id"], audi, day(7), "FIRST_HALF")).status_code == 201
    # Second half doesn't overlap the first half.
    assert (await add_line(me, draft["id"], audi, day(7), "SECOND_HALF")).status_code == 201
    # A full day overlaps both halves.
    response = await add_line(me, draft["id"], audi, day(7), "FULL_DAY")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "LINE_CONFLICT"
    # Same slot on a different date is fine.
    assert (await add_line(me, draft["id"], audi, day(8), "FULL_DAY")).status_code == 201


async def test_same_facility_and_slot_twice_is_rejected(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    await add_line(me, draft["id"], facility_ids["FOOTBALL"], day(2), "09:00-12:00")
    response = await add_line(me, draft["id"], facility_ids["FOOTBALL"], day(2), "09:00-12:00")
    assert response.status_code == 409


# ----- editing -----


async def test_edit_event_details(sign_in):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    response = await me.patch(f"/api/v1/requests/{draft['id']}", json={"participants": 200, "purpose": "Workshop"})
    assert response.status_code == 200
    assert response.json()["event"]["participants"] == 200
    assert response.json()["event"]["purpose"] == "Workshop"
    assert response.json()["event"]["applicant_name"] == EVENT["applicant_name"]


async def test_empty_patch_is_rejected(sign_in):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    assert (await me.patch(f"/api/v1/requests/{draft['id']}", json={})).status_code == 422


async def test_edit_and_remove_lines(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    await add_line(me, draft["id"], facility_ids["M5"], day(10), "FULL_DAY")
    body = (await add_line(me, draft["id"], facility_ids["FOOTBALL"], day(10), "09:00-12:00")).json()
    football = next(line for line in body["lines"] if line["facility_code"] == "FOOTBALL")

    edited = await me.patch(
        f"/api/v1/requests/{draft['id']}/lines/{football['id']}",
        json={"slot_key": "12:00-15:00", "booking_date": day(12)},
    )
    assert edited.status_code == 200
    line = next(item for item in edited.json()["lines"] if item["id"] == football["id"])
    assert (line["slot_key"], line["booking_date"], line["slot_label"]) == ("12:00-15:00", day(12), "12:00–15:00")

    removed = await me.delete(f"/api/v1/requests/{draft['id']}/lines/{football['id']}")
    assert removed.status_code == 200
    assert [item["facility_code"] for item in removed.json()["lines"]] == ["M5"]
    assert removed.json()["charges_preview"]["booking_subtotal"] == 15000


async def test_editing_a_line_into_an_invalid_slot_is_rejected(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    body = (await add_line(me, draft["id"], facility_ids["M5"], day(10), "FULL_DAY")).json()
    line_id = body["lines"][0]["id"]
    response = await me.patch(f"/api/v1/requests/{draft['id']}/lines/{line_id}", json={"slot_key": "SECOND_HALF"})
    assert response.json()["error"]["code"] == "INVALID_SLOT"


async def test_unknown_line_is_not_found(sign_in):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    response = await me.delete(f"/api/v1/requests/{draft['id']}/lines/12345")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "LINE_NOT_FOUND"


async def test_delete_draft(sign_in, facility_ids):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    await add_line(me, draft["id"], facility_ids["M5"], day(10), "FULL_DAY")
    assert (await me.delete(f"/api/v1/requests/{draft['id']}")).status_code == 204
    assert (await me.get(f"/api/v1/requests/{draft['id']}")).status_code == 404
    assert (await me.get("/api/v1/requests")).json()["total"] == 0


async def test_non_draft_requests_cannot_be_edited(sign_in, facility_ids, seeded_db):
    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    body = (await add_line(me, draft["id"], facility_ids["M5"], day(10), "FULL_DAY")).json()
    seeded_db.execute(update(BookingRequest).where(BookingRequest.id == draft["id"]).values(status="SUBMITTED"))
    seeded_db.commit()

    attempts = [
        await me.patch(f"/api/v1/requests/{draft['id']}", json={"purpose": "changed"}),
        await add_line(me, draft["id"], facility_ids["M6"], day(10), "FULL_DAY"),
        await me.delete(f"/api/v1/requests/{draft['id']}/lines/{body['lines'][0]['id']}"),
        await me.delete(f"/api/v1/requests/{draft['id']}"),
    ]
    for response in attempts:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "REQUEST_NOT_EDITABLE"
    detail = (await me.get(f"/api/v1/requests/{draft['id']}")).json()
    assert detail["editable"] is False
    assert detail["event"]["purpose"] == EVENT["purpose"]


async def test_tariff_change_shows_in_draft_preview(sign_in, facility_ids, seeded_db):
    """Drafts preview today's tariff; snapshots are taken only at submission (Week 3)."""
    from app.db.models import Tariff

    me = await sign_in("events@company.com")
    draft = await create_draft(me)
    await add_line(me, draft["id"], facility_ids["M5"], day(10), "FULL_DAY")
    seeded_db.execute(
        update(Tariff)
        .where(Tariff.facility_id == facility_ids["M5"], Tariff.category == "PRIVATE")
        .values(amount=16000)
    )
    seeded_db.commit()
    body = (await me.get(f"/api/v1/requests/{draft['id']}")).json()
    assert body["lines"][0]["rate"]["amount"] == 16000
