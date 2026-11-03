"""Shared helpers for the workflow tests: build a draft, submit it, forward it."""

from datetime import timedelta

from app.core.time import today_ist
from app.services.submission_service import TERMS_VERSION

EVENT = {
    "organisation_name_address": "North Zone Education Society, Chandigarh",
    "applicant_name": "R. Mehta",
    "office_contact": "0172-2345678",
    "mobile": "+91 98765 43210",
    "purpose": "Annual student conference",
    "participants": 180,
}
ACCEPT = {"terms_accepted": True, "terms_version": TERMS_VERSION}


def day(offset: int) -> str:
    return (today_ist() + timedelta(days=offset)).isoformat()


async def draft_with(client, facility_ids: dict[str, int], *lines: tuple[str, int, str]) -> dict:
    """Create a draft with lines given as (facility_code, days_from_today, slot_key)."""
    response = await client.post("/api/v1/requests", json=EVENT)
    assert response.status_code == 201, response.text
    body = response.json()
    for code, offset, slot_key in lines:
        response = await client.post(
            f"/api/v1/requests/{body['id']}/lines",
            json={"facility_id": facility_ids[code], "booking_date": day(offset), "slot_key": slot_key},
        )
        assert response.status_code == 201, response.text
        body = response.json()
    return body


async def submitted(client, facility_ids, *lines) -> dict:
    draft = await draft_with(client, facility_ids, *lines)
    response = await client.post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)
    assert response.status_code == 200, response.text
    return response.json()


async def forwarded(requester, facility_staff, facility_ids, *lines) -> dict:
    request = await submitted(requester, facility_ids, *lines)
    response = await facility_staff.post(f"/api/v1/requests/{request['id']}/forward", json={})
    assert response.status_code == 200, response.text
    return response.json()["request"]


def line_id(request: dict, code: str) -> int:
    return next(line["id"] for line in request["lines"] if line["facility_code"] == code)


async def decide(staff, request_id: int, line: int, decision: str, remark: str | None = None):
    return await staff.post(
        f"/api/v1/requests/{request_id}/decision", json={"line_id": line, "decision": decision, "remark": remark}
    )
