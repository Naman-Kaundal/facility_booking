"""Staff workflow (LLD §8): Facilities review, section decisions, Estate costing, advance intimation.

State machine for a request:

    DRAFT --submit--> SUBMITTED --forward (Facilities)--> WITH_SECTION --all lines decided--> WITH_ESTATE
      ^                   |                                                     \\--all lines rejected--> REJECTED
      |                   +--return (Facilities)--> RETURNED --resubmit--> SUBMITTED
      +-- (requester edits a RETURNED request like a draft)

    WITH_ESTATE --electricity estimate (Estate)--> COSTED --advance intimation (Facilities)--> ADVANCE_INTIMATED
                                          COSTED --revised estimate (Estate)--> COSTED (recalculated)

Lines are routed by facility section: LHC and Auditorium -> ACADEMIC desk, sports grounds ->
SPORTS desk. A mixed request is worked on by both desks in parallel, each seeing only its lines.

Partial rejection policy (assumption, LLD §19 item 6): when every line has a decision, the
request goes to Estate if at least one line was confirmed (rejected lines are simply excluded),
and is REJECTED only if every line was rejected.

Every action is re-validated against the current state (stale or repeated actions get 409),
the request row is locked while it changes, each action writes an audit event, and the
matching emails are queued in the same transaction and sent after it commits.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.time import utc_now
from app.db.models import BookingRequest, RequestLine
from app.repositories.facilities import FacilityRepository
from app.schemas.workflow import DecisionIn, ElectricityIn, IntimateIn, QueueItemOut, QueueOut, StaffRequestOut
from app.services import audit_service, costing_service, settings_service
from app.services.availability_service import AvailabilityService
from app.services.notification_service import Notifier
from app.services.request_service import build_request_out
from app.services.roles_service import SECTION_FOR_ROLE

SECTION_DESKS = ("ACADEMIC", "SPORTS")
# Which requests wait on each desk.
DESK_STATUSES = {
    "FACILITY": ("SUBMITTED", "COSTED"),  # first check, then the advance intimation
    "ESTATE": ("WITH_ESTATE",),
}
ESTATE_VISIBLE = ("WITH_ESTATE", "COSTED", "ADVANCE_INTIMATED")


def _sections(request: BookingRequest) -> list[str]:
    return sorted({line.section_snapshot for line in request.lines if line.section_snapshot})


def _inr(value) -> str:
    return f"₹{value:,.2f}"


class WorkflowService:
    def __init__(self, db: Session, notifier: Notifier | None = None) -> None:
        self.db = db
        self.facilities = FacilityRepository(db)
        self.notifier = notifier

    # ----- queues -----

    def queue(self, desk: str) -> QueueOut:
        if desk in DESK_STATUSES:
            stmt = select(BookingRequest).where(BookingRequest.status.in_(DESK_STATUSES[desk]))
        else:
            # Requests with at least one undecided line for this section.
            stmt = (
                select(BookingRequest)
                .where(BookingRequest.status == "WITH_SECTION")
                .where(
                    BookingRequest.lines.any(
                        (RequestLine.section_snapshot == desk) & (RequestLine.decision == "PENDING")
                    )
                )
            )
        requests = self.db.scalars(stmt.order_by(BookingRequest.submitted_at, BookingRequest.id)).all()
        items = []
        for r in requests:
            pending = 0 if desk not in SECTION_DESKS else sum(
                1 for line in r.lines if line.section_snapshot == desk and line.decision == "PENDING"
            )
            items.append(
                QueueItemOut(
                    id=r.id,
                    ref_no=r.ref_no,
                    status=r.status,
                    purpose=r.purpose,
                    applicant_name=r.applicant_name,
                    organisation=r.organisation_name_address,
                    requester_email=r.contact_email,
                    rate_category=r.rate_category_snapshot,
                    submitted_at=r.submitted_at,
                    line_count=len(r.lines),
                    pending_lines=pending,
                    sections=_sections(r),
                    first_date=min((line.booking_date for line in r.lines), default=None),
                )
            )
        return QueueOut(desk=desk, items=items, total=len(items))

    # ----- staff view -----

    def staff_view(self, request_id: int, roles: list[str]) -> StaffRequestOut:
        request = self._get(request_id)
        if not self._can_view(request, roles):
            # Don't reveal requests outside this person's desks.
            raise AppError("REQUEST_NOT_FOUND", "Request not found.", 404)
        decidable = [
            line.id
            for line in request.lines
            if request.status == "WITH_SECTION"
            and line.decision == "PENDING"
            and any(SECTION_FOR_ROLE.get(role) == line.section_snapshot for role in roles)
        ]
        is_facility = "FACILITY" in roles
        payment_ready = settings_service.payment_url_configured(self.db)
        return StaffRequestOut(
            request=build_request_out(self.facilities, request, request.rate_category_snapshot, include_costs=True),
            requester_name=request.applicant_name,
            requester_email=request.contact_email,
            timeline=audit_service.timeline(self.db, request.id),
            can_forward=is_facility and request.status == "SUBMITTED",
            can_return=is_facility and request.status == "SUBMITTED",
            decidable_line_ids=decidable,
            can_enter_electricity="ESTATE" in roles and request.status in ("WITH_ESTATE", "COSTED"),
            can_intimate=is_facility and request.status == "COSTED" and payment_ready,
            payment_url_configured=payment_ready,
        )

    # ----- Facilities: first check -----

    def forward(self, request_id: int, actor, remark: str | None) -> StaffRequestOut:
        request = self._get(request_id, lock=True)
        self._require_status(request, "SUBMITTED", "forwarded")
        request.status = "WITH_SECTION"
        sections = _sections(request)
        event = audit_service.record(
            self.db, request, "FORWARDED", actor=actor, role="FACILITY",
            from_status="SUBMITTED", to_status="WITH_SECTION",
            remark=remark or f"Sent to: {', '.join(s.title() for s in sections)}",
        )
        if self.notifier:
            self.notifier.notify_requester(request, "REQUEST_FORWARDED", event)
            for section in sections:
                self.notifier.notify_role(section, request, "SECTION_ACTION_REQUIRED", event, note=remark)
        return self._commit_and_reload(request_id, ["FACILITY"])

    def return_for_correction(self, request_id: int, actor, reason: str) -> StaffRequestOut:
        request = self._get(request_id, lock=True)
        self._require_status(request, "SUBMITTED", "returned")
        request.status = "RETURNED"
        request.return_reason = reason
        request.returned_at = utc_now()
        event = audit_service.record(
            self.db, request, "RETURNED", actor=actor, role="FACILITY",
            from_status="SUBMITTED", to_status="RETURNED", remark=reason,
        )
        if self.notifier:
            self.notifier.notify_requester(request, "REQUEST_RETURNED", event, note=f"What to correct: {reason}")
        return self._commit_and_reload(request_id, ["FACILITY"])

    # ----- section decisions -----

    def decide(self, request_id: int, actor, roles: list[str], data: DecisionIn) -> StaffRequestOut:
        request = self._get(request_id, lock=True)
        line = next((ln for ln in request.lines if ln.id == data.line_id), None)
        if line is None:
            raise AppError("LINE_NOT_FOUND", "Facility line not found in this request.", 404)

        role = next((r for r in roles if SECTION_FOR_ROLE.get(r) == line.section_snapshot), None)
        if role is None:
            raise AppError(
                "FORBIDDEN",
                f"This facility is decided by the {(line.section_snapshot or '').title()} section.",
                403,
            )
        self._require_status(request, "WITH_SECTION", "decided on")
        if line.decision != "PENDING":
            raise AppError("LINE_ALREADY_DECIDED", f"This facility was already {line.decision.lower()}.", 409)
        remark = (data.remark or "").strip() or None
        if data.decision == "REJECTED" and not remark:
            raise AppError("REMARK_REQUIRED", "Give a reason for rejecting.", 422, {"field": "remark"})

        if data.decision == "CONFIRMED":
            # Raises SLOT_UNAVAILABLE (409) if an overlapping booking was confirmed first.
            AvailabilityService(self.db).reserve(line)

        line.decision = data.decision
        line.decision_remark = remark
        line.decided_by = actor.id
        line.decided_at = utc_now()
        event = audit_service.record(
            self.db, request, f"LINE_{data.decision}", actor=actor, role=role, remark=remark, line=line,
        )
        if self.notifier:
            name = line.facility_name_snapshot or line.facility.name
            note = f"{name} on {line.booking_date:%d %b %Y}: {data.decision.lower()}"
            if remark:
                note += f" ({remark})"
            self.notifier.notify_requester(request, "SECTION_DECIDED", event, note=note)
            self.notifier.notify_role("FACILITY", request, "SECTION_DECIDED", event, note=note)
        self._advance_if_complete(request)
        return self._commit_and_reload(request_id, roles)

    def _advance_if_complete(self, request: BookingRequest) -> None:
        if any(line.decision == "PENDING" for line in request.lines):
            return
        confirmed = any(line.decision == "CONFIRMED" for line in request.lines)
        new_status = "WITH_ESTATE" if confirmed else "REJECTED"
        event = audit_service.record(
            self.db, request, "STATUS_CHANGED", actor=None, role="SYSTEM",
            from_status=request.status, to_status=new_status,
            remark=(
                "All sections have decided; waiting for Estate's electricity estimate."
                if confirmed
                else "Every facility was rejected."
            ),
        )
        request.status = new_status
        if self.notifier:
            if confirmed:
                self.notifier.notify_role("ESTATE", request, "ESTATE_ACTION_REQUIRED", event)
            else:
                self.notifier.notify_requester(request, "REQUEST_REJECTED", event)

    # ----- Estate: electricity estimate -> costing -----

    def submit_electricity(self, request_id: int, actor, data: ElectricityIn) -> StaffRequestOut:
        request = self._get(request_id, lock=True)
        if request.status not in ("WITH_ESTATE", "COSTED"):
            raise AppError(
                "INVALID_STATE",
                "Estate can enter the electricity estimate only after every section has decided "
                f"(this request is {request.status}).",
                409,
                {"status": request.status},
            )
        revised = request.status == "COSTED"
        remark = (data.remark or "").strip() or None
        cost = costing_service.cost_request(self.db, request, data.electricity_estimate, remark, actor)
        previous = request.status
        request.status = "COSTED"
        audit_service.record(
            self.db, request, "ELECTRICITY_REVISED" if revised else "ELECTRICITY_SUBMITTED", actor=actor,
            role="ESTATE", from_status=previous, to_status="COSTED",
            remark=f"Electricity estimate {_inr(cost.electricity_estimate)}" + (f". {remark}" if remark else ""),
        )
        event = audit_service.record(
            self.db, request, "COST_RECALCULATED" if revised else "COST_CALCULATED", actor=None, role="SYSTEM",
            remark=f"Total estimated cost {_inr(cost.total_estimated_cost)}; advance {_inr(cost.advance_amount)}.",
        )
        if self.notifier:
            self.notifier.notify_role("FACILITY", request, "COST_READY", event)
        return self._commit_and_reload(request_id, ["ESTATE"])

    # ----- Facilities: advance intimation -----

    def intimate(self, request_id: int, actor, data: IntimateIn) -> StaffRequestOut:
        request = self._get(request_id, lock=True)
        self._require_status(request, "COSTED", "intimated")
        settings = settings_service.get(self.db)
        if not settings.payment_url:
            raise AppError(
                "PAYMENT_URL_NOT_CONFIGURED",
                "Ask an admin to set the institute payment link before sending the advance intimation.",
                409,
            )
        cost = request.cost
        cost.payment_url_snapshot = settings.payment_url
        cost.intimated_at = utc_now()
        cost.intimated_by = actor.id
        request.status = "ADVANCE_INTIMATED"
        remark = (data.remark or "").strip() or None
        event = audit_service.record(
            self.db, request, "ADVANCE_INTIMATED", actor=actor, role="FACILITY",
            from_status="COSTED", to_status="ADVANCE_INTIMATED",
            remark=f"Advance {_inr(cost.advance_amount)} intimated" + (f". {remark}" if remark else ""),
        )
        if self.notifier:
            self.notifier.notify_requester(request, "ADVANCE_INTIMATED", event, note=remark)
        return self._commit_and_reload(request_id, ["FACILITY"])

    # ----- helpers -----

    def _get(self, request_id: int, lock: bool = False) -> BookingRequest:
        stmt = select(BookingRequest).where(BookingRequest.id == request_id, BookingRequest.status != "DRAFT")
        if lock:
            stmt = stmt.with_for_update()
        request = self.db.scalars(stmt).first()
        if request is None:
            raise AppError("REQUEST_NOT_FOUND", "Request not found.", 404)
        return request

    @staticmethod
    def _require_status(request: BookingRequest, expected: str, verb: str) -> None:
        if request.status != expected:
            raise AppError(
                "INVALID_STATE", f"This request is {request.status} and can't be {verb} now.", 409,
                {"status": request.status},
            )

    @staticmethod
    def _can_view(request: BookingRequest, roles: list[str]) -> bool:
        if "FACILITY" in roles or "ADMIN" in roles:
            return True
        if "ESTATE" in roles and request.status in ESTATE_VISIBLE:
            return True
        sections = {SECTION_FOR_ROLE[r] for r in roles if r in SECTION_FOR_ROLE}
        if not sections or request.status in ("SUBMITTED", "RETURNED"):
            return False  # sections only see requests Facilities has forwarded
        return any(line.section_snapshot in sections for line in request.lines)

    def _commit_and_reload(self, request_id: int, roles: list[str]) -> StaffRequestOut:
        self.db.commit()
        if self.notifier:
            self.notifier.send_queued()  # after the commit: a failed email never undoes the action
        self.db.expire_all()
        return self.staff_view(request_id, roles)

