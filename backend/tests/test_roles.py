"""Role-based access: every desk action is checked on the server (LLD §3.2, §17.1)."""

import pytest
from sqlalchemy import select

from app.db.models import Facility
from app.services import roles_service
from tests.helpers import decide, forwarded, line_id, submitted


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


@pytest.fixture
async def people(sign_in):
    return {
        "requester": await sign_in("events@company.com"),
        "facility": await sign_in("facilities@iitrpr.ac.in", roles=("FACILITY",)),
        "academic": await sign_in("academic@iitrpr.ac.in", roles=("ACADEMIC",)),
        "sports": await sign_in("sports@iitrpr.ac.in", roles=("SPORTS",)),
    }


async def test_me_lists_active_roles(people):
    assert (await people["facility"].get("/api/v1/users/me")).json()["roles"] == ["FACILITY"]
    assert (await people["requester"].get("/api/v1/users/me")).json()["roles"] == []


async def test_requesters_cannot_use_any_desk(people, facility_ids):
    request = await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    me = people["requester"]
    for response in (
        await me.get("/api/v1/workflow/queue", params={"desk": "FACILITY"}),
        await me.get(f"/api/v1/workflow/requests/{request['id']}"),
        await me.post(f"/api/v1/requests/{request['id']}/forward", json={}),
        await me.post(f"/api/v1/requests/{request['id']}/return", json={"reason": "x"}),
        await decide(me, request["id"], line_id(request, "M5"), "CONFIRMED"),
    ):
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "FORBIDDEN"


async def test_section_staff_cannot_forward_or_return(people, facility_ids):
    request = await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    response = await people["academic"].post(f"/api/v1/requests/{request['id']}/forward", json={})
    assert response.status_code == 403


async def test_facilities_cannot_decide_lines(people, facility_ids):
    request = await forwarded(people["requester"], people["facility"], facility_ids, ("M5", 10, "FULL_DAY"))
    response = await decide(people["facility"], request["id"], line_id(request, "M5"), "CONFIRMED")
    assert response.status_code == 403


async def test_academic_cannot_decide_a_sports_line(people, facility_ids):
    request = await forwarded(
        people["requester"], people["facility"], facility_ids, ("M5", 10, "FULL_DAY"), ("HOCKEY", 10, "09:00-12:00")
    )
    response = await decide(people["academic"], request["id"], line_id(request, "HOCKEY"), "CONFIRMED")
    assert response.status_code == 403
    response = await decide(people["sports"], request["id"], line_id(request, "M5"), "CONFIRMED")
    assert response.status_code == 403


async def test_desk_queue_requires_that_desks_role(people):
    response = await people["academic"].get("/api/v1/workflow/queue", params={"desk": "SPORTS"})
    assert response.status_code == 403


async def test_section_staff_only_see_requests_with_their_lines(people, facility_ids):
    sports_only = await forwarded(people["requester"], people["facility"], facility_ids, ("CRICKET", 5, "PER_DAY"))
    response = await people["academic"].get(f"/api/v1/workflow/requests/{sports_only['id']}")
    assert response.status_code == 404


async def test_inactive_role_has_no_access(people, session_factory):
    with session_factory() as db:
        roles_service.revoke(db, "academic@iitrpr.ac.in", "ACADEMIC")
    response = await people["academic"].get("/api/v1/workflow/queue", params={"desk": "ACADEMIC"})
    assert response.status_code == 403
    assert (await people["academic"].get("/api/v1/users/me")).json()["roles"] == []


async def test_one_person_can_hold_several_roles(sign_in):
    both = await sign_in("lead@iitrpr.ac.in", roles=("FACILITY", "ACADEMIC"))
    assert (await both.get("/api/v1/users/me")).json()["roles"] == ["ACADEMIC", "FACILITY"]
    assert (await both.get("/api/v1/workflow/queue", params={"desk": "ACADEMIC"})).status_code == 200


def test_grant_is_idempotent_and_reactivates(session_factory):
    with session_factory() as db:
        roles_service.grant(db, "Someone@IITRPR.ac.in", "sports")
        roles_service.grant(db, "someone@iitrpr.ac.in", "SPORTS")
        assert roles_service.active_roles(db, "someone@iitrpr.ac.in") == ["SPORTS"]
        roles_service.revoke(db, "someone@iitrpr.ac.in", "SPORTS")
        assert roles_service.active_roles(db, "someone@iitrpr.ac.in") == []
        roles_service.grant(db, "someone@iitrpr.ac.in", "SPORTS")
        assert roles_service.active_roles(db, "someone@iitrpr.ac.in") == ["SPORTS"]


def test_unknown_role_is_refused(session_factory):
    from app.core.errors import AppError

    with session_factory() as db, pytest.raises(AppError):
        roles_service.grant(db, "someone@iitrpr.ac.in", "PRINCIPAL")
