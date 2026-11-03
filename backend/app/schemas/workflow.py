from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.request import RequestOut, TimelineEventOut

Desk = Literal["FACILITY", "ACADEMIC", "SPORTS"]

_INPUT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class QueueItemOut(BaseModel):
    id: int
    ref_no: str | None
    status: str
    purpose: str
    applicant_name: str
    organisation: str
    requester_email: str
    rate_category: str | None
    submitted_at: datetime | None
    line_count: int
    # Lines this desk still has to decide (Academic/Sports desks); 0 on the Facilities desk.
    pending_lines: int
    sections: list[str]
    first_date: date | None


class QueueOut(BaseModel):
    desk: Desk
    items: list[QueueItemOut]
    total: int


class StaffRequestOut(BaseModel):
    request: RequestOut
    requester_name: str
    requester_email: str
    timeline: list[TimelineEventOut]
    # What the signed-in staff member may do right now (the backend re-checks on every action).
    can_forward: bool
    can_return: bool
    decidable_line_ids: list[int]


class ForwardIn(BaseModel):
    model_config = _INPUT

    remark: str | None = Field(default=None, max_length=1000)


class ReturnIn(BaseModel):
    model_config = _INPUT

    reason: str = Field(min_length=1, max_length=1000)


class DecisionIn(BaseModel):
    model_config = _INPUT

    line_id: int = Field(gt=0)
    decision: Literal["CONFIRMED", "REJECTED"]
    remark: str | None = Field(default=None, max_length=1000)
