"""Availability and conflict prevention (LLD §6.2, §17.2)."""

from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError

from app.db.models import BookingRequest, Facility, RequestLine, Reservation, User
from tests.helpers import ACCEPT, day, decide, draft_with, forwarded, line_id, submitted


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


@pytest.fixture
async def people(sign_in):
    return {
        "requester": await sign_in("events@company.com"),
        "other": await sign_in("other@company.com"),
        "facility": await sign_in("facilities@iitrpr.ac.in", roles=("FACILITY",)),
        "academic": await sign_in("academic@iitrpr.ac.in", roles=("ACADEMIC",)),
        "sports": await sign_in("sports@iitrpr.ac.in", roles=("SPORTS",)),
    }


async def availability(client, facility_id: int, date: str) -> dict[str, bool]:
    response = await client.get("/api/v1/availability", params={"facility_id": facility_id, "date": date})
    assert response.status_code == 200, response.text
    return {s["slot_key"]: s["available"] for s in response.json()["slots"]}


async def confirm(people, facility_ids, code, offset, slot_key, staff="academic") -> dict:
    request = await forwarded(people["requester"], people["facility"], facility_ids, (code, offset, slot_key))
    response = await decide(people[staff], request["id"], line_id(request, code), "CONFIRMED")
    assert response.status_code == 200, response.text
    return response.json()["request"]


async def test_everything_is_free_initially(client, facility_ids):
    slots = await availability(client, facility_ids["AUDI_COMPLETE"], day(7))
    assert slots == {"FULL_DAY": True, "FIRST_HALF": True, "SECOND_HALF": True}


async def test_drafts_and_pending_requests_do_not_hold_slots(people, facility_ids, client):
    await draft_with(people["requester"], facility_ids, ("M5", 7, "FULL_DAY"))
    await submitted(people["other"], facility_ids, ("M5", 7, "FULL_DAY"))
    assert await availability(client, facility_ids["M5"], day(7)) == {"FULL_DAY": True}


async def test_confirmed_full_day_blocks_every_slot_that_day(people, facility_ids, client):
    await confirm(people, facility_ids, "AUDI_COMPLETE", 7, "FULL_DAY")
    assert await availability(client, facility_ids["AUDI_COMPLETE"], day(7)) == {
        "FULL_DAY": False,
        "FIRST_HALF": False,
        "SECOND_HALF": False,
    }
    # Other dates and other facilities are unaffected.
    assert all((await availability(client, facility_ids["AUDI_COMPLETE"], day(8))).values())
    assert all((await availability(client, facility_ids["M5"], day(7))).values())


async def test_first_half_leaves_second_half_free_but_blocks_full_day(people, facility_ids, client):
    await confirm(people, facility_ids, "AUDI_COMPLETE", 7, "FIRST_HALF")
    assert await availability(client, facility_ids["AUDI_COMPLETE"], day(7)) == {
        "FULL_DAY": False,
        "FIRST_HALF": False,
        "SECOND_HALF": True,
    }
    # So a second request can still get the second half.
    await confirm(people, facility_ids, "AUDI_COMPLETE", 7, "SECOND_HALF")


async def test_adjacent_three_hour_windows_do_not_clash(people, facility_ids, client):
    await confirm(people, facility_ids, "FOOTBALL", 3, "09:00-12:00", staff="sports")
    assert await availability(client, facility_ids["FOOTBALL"], day(3)) == {
        "09:00-12:00": False,
        "12:00-15:00": True,
        "15:00-18:00": True,
    }


async def test_second_confirmation_of_the_same_slot_is_refused(people, facility_ids):
    # Two different requests for the same slot both reach the Academic desk...
    first = await forwarded(people["requester"], people["facility"], facility_ids, ("M5", 9, "FULL_DAY"))
    second = await forwarded(people["other"], people["facility"], facility_ids, ("M5", 9, "FULL_DAY"))
    ok = await decide(people["academic"], first["id"], line_id(first, "M5"), "CONFIRMED")
    assert ok.status_code == 200
    # ...but only one can be confirmed.
    clash = await decide(people["academic"], second["id"], line_id(second, "M5"), "CONFIRMED")
    assert clash.status_code == 409
    assert clash.json()["error"]["code"] == "SLOT_UNAVAILABLE"
    view = (await people["academic"].get(f"/api/v1/workflow/requests/{second['id']}")).json()
    assert view["request"]["lines"][0]["decision"] == "PENDING"  # still waiting; can be rejected instead


async def test_submitting_an_already_booked_slot_is_refused(people, facility_ids):
    await confirm(people, facility_ids, "M6", 4, "FULL_DAY")
    draft = await draft_with(people["other"], facility_ids, ("M6", 4, "FULL_DAY"))
    response = await people["other"].post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "SLOT_UNAVAILABLE"


async def test_rejected_lines_do_not_block_the_slot(people, facility_ids, client):
    request = await forwarded(people["requester"], people["facility"], facility_ids, ("M3", 6, "FULL_DAY"))
    response = await decide(people["academic"], request["id"], line_id(request, "M3"), "REJECTED", "Exam day")
    assert response.status_code == 200
    assert await availability(client, facility_ids["M3"], day(6)) == {"FULL_DAY": True}


def test_database_refuses_overlapping_reservations(seeded_db):
    """The exclusion constraint is the last line of defence, even against concurrent writers."""
    m5 = seeded_db.scalar(select(Facility.id).where(Facility.code == "M5"))
    # Reservations belong to request lines, so create two minimal requests directly.
    user = User(google_sub="x", email="x@company.com", name="X", rate_category="PRIVATE")
    seeded_db.add(user)
    seeded_db.flush()
    made = []
    for _ in range(2):
        req = BookingRequest(
            user_id=user.id, status="WITH_SECTION", organisation_name_address="Org", applicant_name="X",
            contact_email=user.email, office_contact="0172-2345678", mobile="9876543210", purpose="P",
            participants=10,
        )
        req.lines.append(RequestLine(facility_id=m5, booking_date=date(2030, 1, 1), slot_key="FULL_DAY"))
        seeded_db.add(req)
        seeded_db.flush()
        made.append(req.lines[0].id)

    whole_day = Range(datetime(2030, 1, 1), datetime(2030, 1, 2), bounds="[)")
    morning = Range(datetime(2030, 1, 1, 9), datetime(2030, 1, 1, 12), bounds="[)")
    seeded_db.add(Reservation(request_line_id=made[0], facility_id=m5, during=whole_day))
    seeded_db.commit()
    seeded_db.add(Reservation(request_line_id=made[1], facility_id=m5, during=morning))
    with pytest.raises(IntegrityError, match="ex_reservations_no_overlap"):
        seeded_db.commit()


async def test_unknown_facility_availability_is_404(client):
    response = await client.get("/api/v1/availability", params={"facility_id": 999999, "date": day(1)})
    assert response.status_code == 404
