"""The cost breakdown shown to staff and, after the advance intimation, to the requester."""

from datetime import date, datetime

from pydantic import BaseModel


class CostItemOut(BaseModel):
    line_id: int
    facility_name: str
    booking_date: date
    slot_label: str
    amount: float


class CostBreakdownOut(BaseModel):
    items: list[CostItemOut]  # the confirmed facilities and the rates frozen at submission
    booking_subtotal: float
    gst_pct: float
    gst_amount: float
    cleaning_pct: float
    cleaning_amount: float
    security_deposit: float
    electricity_estimate: float
    electricity_advance_pct: float
    electricity_advance: float
    total_estimated_cost: float
    advance_amount: float
    estimate_remark: str | None
    calculated_at: datetime
    calculated_by_name: str | None
    intimated_at: datetime | None
    # Only filled once Facilities has sent the advance intimation.
    payment_url: str | None
    is_final: bool
