"""Workflow emails (LLD §14, §17.5): right recipients at each stage, logged, retried, never duplicated."""

import pytest
from sqlalchemy import select

from app.db.models import EmailLog, Facility
from tests.helpers import ACCEPT, decide, draft_with, enter_electricity, set_payment_url, submitted, with_estate

REQUESTER = "events@company.com"
FACILITY = "facilities@iitrpr.ac.in"
ACADEMIC = "academic@iitrpr.ac.in"
SPORTS = "sports@iitrpr.ac.in"
ESTATE = "estate@iitrpr.ac.in"


@pytest.fixture
def facility_ids(seeded_db) -> dict[str, int]:
    return dict(seeded_db.execute(select(Facility.code, Facility.id)).all())


@pytest.fixture
async def people(sign_in):
    return {
        "requester": await sign_in(REQUESTER, name="Asha Rao"),
        "facility": await sign_in(FACILITY, name="Facilities Desk", roles=("FACILITY",)),
        "academic": await sign_in(ACADEMIC, name="Academic Desk", roles=("ACADEMIC",)),
        "sports": await sign_in(SPORTS, name="Sports Desk", roles=("SPORTS",)),
        "estate": await sign_in(ESTATE, name="Estate Desk", roles=("ESTATE",)),
        "admin": await sign_in("admin@iitrpr.ac.in", name="Admin", roles=("ADMIN",)),
    }


def logs(db) -> list[EmailLog]:
    db.expire_all()
    return list(db.scalars(select(EmailLog).order_by(EmailLog.id)))


async def test_emails_at_every_stage(people, facility_ids, outbox):
    request = await submitted(
        people["requester"], facility_ids, ("M5", 10, "FULL_DAY"), ("FOOTBALL", 11, "15:00-18:00")
    )
    ref = request["ref_no"]
    assert outbox.subjects(REQUESTER) == [f"[Facility Booking] Request {ref} received"]
    assert outbox.subjects(FACILITY) == [f"[Facility Booking] New request {ref} to review"]
    assert ref in outbox.to(REQUESTER)[0].text and "LHC Classroom M5" in outbox.to(REQUESTER)[0].text
    assert f"/requests/{request['id']}" in outbox.to(REQUESTER)[0].text  # link back to the app

    await people["facility"].post(f"/api/v1/requests/{request['id']}/forward", json={})
    # Mixed request: both sections are asked, plus a status update for the requester.
    assert len(outbox.to(ACADEMIC)) == 1 and len(outbox.to(SPORTS)) == 1
    assert "desk=ACADEMIC" in outbox.to(ACADEMIC)[0].text
    assert outbox.subjects(REQUESTER)[-1].endswith("sent to the sections")

    lines = {line["facility_code"]: line["id"] for line in request["lines"]}
    await decide(people["academic"], request["id"], lines["M5"], "CONFIRMED")
    await decide(people["sports"], request["id"], lines["FOOTBALL"], "CONFIRMED")
    assert len(outbox.to(ESTATE)) == 1  # all sections decided -> Estate is asked
    assert "electricity estimate needed" in outbox.to(ESTATE)[0].subject

    await enter_electricity(people["estate"], request["id"], 2500)
    assert outbox.subjects(FACILITY)[-1].endswith("costs ready to review")

    await set_payment_url(people["admin"], "https://payments.example.org/test-only")
    await people["facility"].post(f"/api/v1/requests/{request['id']}/intimate", json={})
    final = outbox.to(REQUESTER)[-1]
    assert final.subject.endswith("advance payment details")
    assert "₹30,040.00" in final.text and "https://payments.example.org/test-only" in final.text
    assert "https://payments.example.org/test-only" in final.html


async def test_returned_and_rejected_emails_give_the_reason(people, facility_ids, outbox):
    request = await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    await people["facility"].post(f"/api/v1/requests/{request['id']}/return", json={"reason": "Add the address"})
    assert "Add the address" in outbox.to(REQUESTER)[-1].text

    await people["requester"].post(f"/api/v1/requests/{request['id']}/submit", json=ACCEPT)
    await people["facility"].post(f"/api/v1/requests/{request['id']}/forward", json={})
    await decide(people["academic"], request["id"], request["lines"][0]["id"], "REJECTED", "Exams that week")
    last = outbox.to(REQUESTER)[-1]
    assert last.subject.endswith("could not be approved")
    assert any("Exams that week" in m.text for m in outbox.to(REQUESTER))


async def test_every_email_is_logged(people, facility_ids, seeded_db):
    await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    rows = logs(seeded_db)
    assert {(r.event, r.recipient, r.status, r.attempt_count) for r in rows} == {
        ("REQUEST_SUBMITTED", REQUESTER, "SENT", 1),
        ("FACILITY_REVIEW_REQUIRED", FACILITY, "SENT", 1),
    }
    assert all(r.sent_at is not None and r.last_error is None for r in rows)


async def test_failed_email_is_logged_and_retried_without_blocking_the_workflow(
    people, facility_ids, outbox, seeded_db
):
    outbox.fail_next = 2  # SMTP is down for both submission emails
    draft = await draft_with(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    response = await people["requester"].post(f"/api/v1/requests/{draft['id']}/submit", json=ACCEPT)
    assert response.status_code == 200  # the submission still succeeded
    failed = [r for r in logs(seeded_db) if r.status == "FAILED"]
    assert len(failed) == 2 and "SMTP server unavailable" in failed[0].last_error

    # Admin sees them and retries once SMTP is back.
    listed = (await people["admin"].get("/api/v1/admin/emails", params={"status": "FAILED"})).json()
    assert listed["total"] == 2
    report = (await people["admin"].post("/api/v1/admin/emails/retry")).json()
    assert report == {"sent": 2, "failed": 0, "skipped": 0}
    assert {(r.status, r.attempt_count) for r in logs(seeded_db)} == {("SENT", 2)}
    assert len(outbox.to(REQUESTER)) == 1  # exactly one copy arrived


async def test_retries_are_bounded(people, facility_ids, outbox, seeded_db, settings):
    outbox.fail_next = 100
    await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    for _ in range(settings.email_max_attempts + 2):
        await people["admin"].post("/api/v1/admin/emails/retry")
    assert {r.attempt_count for r in logs(seeded_db)} == {settings.email_max_attempts}
    assert outbox.sent == []


async def test_no_duplicate_emails_for_one_event(people, facility_ids, outbox, seeded_db):
    await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    # Retrying when everything was already sent does nothing.
    report = (await people["admin"].post("/api/v1/admin/emails/retry")).json()
    assert report["sent"] == 0
    assert len(outbox.to(REQUESTER)) == 1
    keys = [r.idempotency_key for r in logs(seeded_db)]
    assert len(keys) == len(set(keys))


async def test_inactive_staff_get_no_emails(people, facility_ids, outbox, sign_in):
    old = await sign_in("old-facilities@iitrpr.ac.in", roles=("FACILITY",))
    roles = (await people["admin"].get("/api/v1/admin/staff-roles")).json()
    role_id = next(r["id"] for r in roles if r["email"] == "old-facilities@iitrpr.ac.in")
    await people["admin"].patch(f"/api/v1/admin/staff-roles/{role_id}", json={"active": False})
    await submitted(people["requester"], facility_ids, ("M5", 10, "FULL_DAY"))
    assert outbox.to("old-facilities@iitrpr.ac.in") == []
    assert len(outbox.to(FACILITY)) == 1
    assert (await old.get("/api/v1/workflow/queue", params={"desk": "FACILITY"})).status_code == 403


async def test_estate_email_only_when_every_section_has_decided(people, facility_ids, outbox):
    await with_estate(people, facility_ids, ("M5", 10, "FULL_DAY"), ("FOOTBALL", 11, "15:00-18:00"))
    assert len(outbox.to(ESTATE)) == 1
