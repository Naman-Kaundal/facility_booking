"""Staff desk endpoints. Every route checks the caller's role on the server."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import StaffContext, get_notifier, require_role
from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.workflow import (
    DecisionIn,
    Desk,
    ElectricityIn,
    ForwardIn,
    IntimateIn,
    QueueOut,
    ReturnIn,
    StaffRequestOut,
)
from app.services.notification_service import Notifier
from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["workflow"])

any_desk = require_role("FACILITY", "ACADEMIC", "SPORTS", "ESTATE", "ADMIN")
facility_desk = require_role("FACILITY")
section_desk = require_role("ACADEMIC", "SPORTS")
estate_desk = require_role("ESTATE")


def get_workflow(db: Session = Depends(get_db), notifier: Notifier = Depends(get_notifier)) -> WorkflowService:
    return WorkflowService(db, notifier)


@router.get("/workflow/queue", response_model=QueueOut)
def desk_queue(
    desk: Desk = Query(..., description="FACILITY, ACADEMIC, SPORTS or ESTATE"),
    staff: StaffContext = Depends(any_desk),
    service: WorkflowService = Depends(get_workflow),
) -> QueueOut:
    """Requests waiting for this desk: Facilities sees SUBMITTED and COSTED requests; Academic/Sports
    see forwarded requests that still have undecided lines for their section; Estate sees WITH_ESTATE."""
    if desk not in staff.roles:
        raise AppError("FORBIDDEN", f"You don't have the {desk} role.", 403)
    return service.queue(desk)


@router.get("/workflow/requests/{request_id}", response_model=StaffRequestOut)
def staff_request_view(
    request_id: int, staff: StaffContext = Depends(any_desk), service: WorkflowService = Depends(get_workflow)
) -> StaffRequestOut:
    return service.staff_view(request_id, staff.roles)


@router.post("/requests/{request_id}/forward", response_model=StaffRequestOut)
def forward_request(
    request_id: int,
    body: ForwardIn,
    staff: StaffContext = Depends(facility_desk),
    service: WorkflowService = Depends(get_workflow),
) -> StaffRequestOut:
    """Facilities: send each line to its section (Academic and/or Sports)."""
    return service.forward(request_id, staff.user, body.remark)


@router.post("/requests/{request_id}/return", response_model=StaffRequestOut)
def return_request(
    request_id: int,
    body: ReturnIn,
    staff: StaffContext = Depends(facility_desk),
    service: WorkflowService = Depends(get_workflow),
) -> StaffRequestOut:
    """Facilities: send an incomplete request back to the requester with a reason."""
    return service.return_for_correction(request_id, staff.user, body.reason)


@router.post("/requests/{request_id}/decision", response_model=StaffRequestOut)
def decide_line(
    request_id: int,
    body: DecisionIn,
    staff: StaffContext = Depends(section_desk),
    service: WorkflowService = Depends(get_workflow),
) -> StaffRequestOut:
    """Academic/Sports: confirm or reject one of their own section's lines."""
    return service.decide(request_id, staff.user, staff.roles, body)


@router.post("/requests/{request_id}/electricity", response_model=StaffRequestOut)
def submit_electricity(
    request_id: int,
    body: ElectricityIn,
    staff: StaffContext = Depends(estate_desk),
    service: WorkflowService = Depends(get_workflow),
) -> StaffRequestOut:
    """Estate: enter (or revise) the approximate electricity charge. The server then calculates every cost."""
    return service.submit_electricity(request_id, staff.user, body)


@router.post("/requests/{request_id}/intimate", response_model=StaffRequestOut)
def intimate_advance(
    request_id: int,
    body: IntimateIn,
    staff: StaffContext = Depends(facility_desk),
    service: WorkflowService = Depends(get_workflow),
) -> StaffRequestOut:
    """Facilities: send the requester the cost breakdown, the advance and the institute payment link."""
    return service.intimate(request_id, staff.user, body)
