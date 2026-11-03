"""Submitting a draft (or a request returned for correction) to Facilities.

On submission the backend:
1. checks the requester accepted the current terms version;
2. re-validates every line (date, facility, slot, tariff) and checks no line clashes with a
   booking that has already been confirmed;
3. freezes the rate category, tariff and facility details on each line (snapshots), so later
   tariff or profile changes can't alter the request;
4. assigns a reference number FB-YYYY-NNN from an atomic counter (first submission only);
5. moves the request to SUBMITTED and records the event in the audit log.
"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import start_of_day_ist, today_ist, utc_now
from app.db.models import BookingRequest, ReferenceCounter, User
from app.repositories.facilities import FacilityRepository
from app.schemas.request import RequestOut, SubmitIn, TermsOut
from app.services import audit_service
from app.services.availability_service import AvailabilityService
from app.services.request_service import EDITABLE_STATUSES, RequestService

# Placeholder until DR Facilities supplies the approved terms (LLD §19 item 9). Bump the version
# whenever the text changes: requesters must accept the version that is current at submission.
TERMS_VERSION = "v1-placeholder"
TERMS_TEXT = """PLACEHOLDER TERMS — to be replaced with the terms approved by the Facilities Section.

1. The booking is confirmed only after the concerned section approves each facility and the
   advance intimated by Facilities is paid through the institute's payment link.
2. Charges are as per the institute tariff for the requester's category. GST, cleaning
   charges, a refundable security deposit and electricity charges are added when the request
   is costed.
3. The requester is responsible for the premises, furniture and equipment during the event
   and for any damage caused.
4. Facilities must be vacated on time and left clean. Decoration must not damage walls,
   floors or fittings.
5. The institute may cancel or reschedule a booking for academic or administrative reasons.
6. Smoking, alcohol and prohibited substances are not allowed on campus.
"""
MAX_LINES = 20


def current_terms() -> TermsOut:
    return TermsOut(version=TERMS_VERSION, text=TERMS_TEXT, is_placeholder=TERMS_VERSION.endswith("placeholder"))


def next_reference(db: Session, year: int) -> str:
    """Atomically take the next number for the year: INSERT ... ON CONFLICT DO UPDATE ... RETURNING.

    Two simultaneous submissions each get their own number; PostgreSQL serialises the update.
    """
    stmt = (
        insert(ReferenceCounter)
        .values(year=year, last_value=1)
        .on_conflict_do_update(
            index_elements=[ReferenceCounter.year], set_={"last_value": ReferenceCounter.last_value + 1}
        )
        .returning(ReferenceCounter.last_value)
    )
    value = db.execute(stmt).scalar_one()
    return f"FB-{year}-{value:03d}"


class SubmissionService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.requests = RequestService(db)
        self.facilities = FacilityRepository(db)
        self.availability = AvailabilityService(db)

    def submit(self, user: User, request_id: int, data: SubmitIn) -> RequestOut:
        # Lock the row so a double-click or two tabs can't submit twice.
        request = self.db.scalars(
            select(BookingRequest)
            .where(BookingRequest.id == request_id, BookingRequest.user_id == user.id)
            .with_for_update()
        ).first()
        if request is None:
            raise AppError("REQUEST_NOT_FOUND", "Request not found.", 404)
        if request.status not in EDITABLE_STATUSES:
            raise AppError("INVALID_STATE", f"This request is already {request.status}.", 409)
        if not data.terms_accepted:
            raise AppError(
                "TERMS_REQUIRED", "Please accept the terms and conditions.", 422, {"field": "terms_accepted"}
            )
        if data.terms_version != TERMS_VERSION:
            raise AppError(
                "TERMS_OUTDATED", "The terms have changed. Please review and accept the current version.", 422,
                {"current_version": TERMS_VERSION},
            )
        if user.rate_category is None:
            raise AppError("PROFILE_INCOMPLETE", "Choose your organisation category before submitting.", 409)
        if not request.lines:
            raise AppError("NO_LINES", "Add at least one facility before submitting.", 422)
        if len(request.lines) > MAX_LINES:
            raise AppError("TOO_MANY_LINES", f"A request can have at most {MAX_LINES} facilities.", 422)

        for line in request.lines:
            # Same checks as when the line was added (dates may have passed, tariffs may have changed).
            slot = self.requests.validate_line(
                user, request, line.facility_id, line.booking_date, line.slot_key, exclude_line_id=line.id
            )
            if not self.availability.is_free(line.facility_id, line.booking_date, slot):
                raise AppError(
                    "SLOT_UNAVAILABLE",
                    f"{line.facility.name} is already booked on {line.booking_date:%d %b %Y} ({slot.label}). "
                    "Change or remove that facility and submit again.",
                    409,
                    {"line_id": line.id},
                )
            tariff = self.facilities.effective_tariff(
                line.facility_id, user.rate_category, slot.slot_type, start_of_day_ist(line.booking_date)
            )
            line.facility_code_snapshot = line.facility.code
            line.facility_name_snapshot = line.facility.name
            line.section_snapshot = line.facility.section
            line.slot_label_snapshot = slot.label
            line.rate_category_snapshot = user.rate_category
            line.tariff_id_snapshot = tariff.id
            line.unit_snapshot = tariff.unit
            line.line_amount_snapshot = tariff.amount
            line.decision = "PENDING"
            line.decision_remark = None
            line.decided_by = None
            line.decided_at = None

        previous = request.status
        resubmission = request.ref_no is not None
        if not resubmission:
            request.ref_no = next_reference(self.db, today_ist().year)
        request.status = "SUBMITTED"
        request.submitted_at = utc_now()
        request.rate_category_snapshot = user.rate_category
        request.terms_version = data.terms_version
        request.terms_accepted_at = utc_now()
        audit_service.record(
            self.db, request, "RESUBMITTED" if resubmission else "SUBMITTED",
            actor=user, role="REQUESTER", from_status=previous, to_status="SUBMITTED",
        )
        self.db.commit()
        self.db.expire_all()
        return self.requests.detail(user, request.id)
