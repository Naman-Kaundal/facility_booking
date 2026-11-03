"""Staff desk endpoints. Every route checks the caller's role on the server."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import StaffContext, require_role
from app.core.errors import AppError
from app.db.session import get_db
from app.schemas.workflow import DecisionIn, Desk, ForwardIn, QueueOut, ReturnIn, StaffRequestOut
from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["workflow"])

any_desk = require_role("FACILITY", "ACADEMIC", "SPORTS", "ADMIN")
facility_desk = require_role("FACILITY")
section_desk = require_role("ACADEMIC", "SPORTS")


def get_workflow(db: Session = Depends(get_db)) -> WorkflowService:
    return WorkflowService(db)


@router.get("/workflow/queue", response_model=QueueOut)
def desk_queue(
    desk: Desk = Query(..., description="FACILITY, ACADEMIC or SPORTS"),
    staff: StaffContext = Depends(any_desk),
    service: WorkflowService = Depends(get_workflow),
) -> QueueOut:
    """Requests waiting for this desk: Facilities sees SUBMITTED requests; Academic/Sports see
    forwarded requests that still have undecided lines for their section."""
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
