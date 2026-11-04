"""Costing engine (LLD §9.2). All amounts are calculated here, never taken from the browser.

    B  = booking subtotal: sum of the tariff snapshots of the CONFIRMED lines
    G  = GST %             C = cleaning %          D = security deposit (per request)
    E  = Estate's electricity estimate             P = % of electricity collected in advance

    gst_amount           = round(B × G / 100, 2)
    cleaning_amount      = round(B × C / 100, 2)
    electricity_advance  = round(E × P / 100, 2)
    total_estimated_cost = B + gst + cleaning + D + E
    advance_amount       = B + gst + cleaning + D + electricity_advance

Rounding is half-up to the paisa. Rejected lines are excluded. A "No charges" line (₹0) adds
nothing. Assumptions to confirm with DR Facilities (LLD §9.1): GST and cleaning apply to every
facility type, and the deposit is charged once per request.
"""

from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models import BookingRequest, RequestCost, User
from app.schemas.costs import CostBreakdownOut, CostItemOut
from app.services import settings_service

PAISA = Decimal("0.01")
HUNDRED = Decimal(100)


def money(value) -> Decimal:
    return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Breakdown:
    booking_subtotal: Decimal
    gst_pct: Decimal
    gst_amount: Decimal
    cleaning_pct: Decimal
    cleaning_amount: Decimal
    security_deposit: Decimal
    electricity_estimate: Decimal
    electricity_advance_pct: Decimal
    electricity_advance: Decimal
    total_estimated_cost: Decimal
    advance_amount: Decimal


def calculate(
    booking_subtotal,
    *,
    gst_pct,
    cleaning_pct,
    security_deposit,
    electricity_estimate,
    electricity_advance_pct,
) -> Breakdown:
    """Pure calculation, so it can be unit-tested without a database."""
    b = money(booking_subtotal)
    g, c, p = Decimal(gst_pct), Decimal(cleaning_pct), Decimal(electricity_advance_pct)
    d = money(security_deposit)
    e = money(electricity_estimate)
    for name, value in (("booking subtotal", b), ("security deposit", d), ("electricity estimate", e)):
        if value < 0:
            raise ValueError(f"The {name} can't be negative.")
    for name, value in (("GST", g), ("cleaning", c), ("electricity advance", p)):
        if not 0 <= value <= 100:
            raise ValueError(f"The {name} percentage must be between 0 and 100.")
    gst = money(b * g / HUNDRED)
    cleaning = money(b * c / HUNDRED)
    electricity_advance = money(e * p / HUNDRED)
    return Breakdown(
        booking_subtotal=b,
        gst_pct=g,
        gst_amount=gst,
        cleaning_pct=c,
        cleaning_amount=cleaning,
        security_deposit=d,
        electricity_estimate=e,
        electricity_advance_pct=p,
        electricity_advance=electricity_advance,
        total_estimated_cost=b + gst + cleaning + d + e,
        advance_amount=b + gst + cleaning + d + electricity_advance,
    )


def booking_subtotal(request: BookingRequest) -> Decimal:
    """Sum of the rates frozen at submission, for the lines a section confirmed."""
    return money(sum((line.line_amount_snapshot or 0) for line in request.lines if line.decision == "CONFIRMED"))


def cost_request(
    db: Session, request: BookingRequest, electricity_estimate, remark: str | None, actor: User
) -> RequestCost:
    """Calculate with the current settings and store the result (replacing an earlier calculation)."""
    settings = settings_service.get(db)
    breakdown = calculate(
        booking_subtotal(request),
        gst_pct=settings.gst_pct,
        cleaning_pct=settings.cleaning_pct,
        security_deposit=settings.security_deposit,
        electricity_estimate=electricity_estimate,
        electricity_advance_pct=settings.electricity_advance_pct,
    )
    cost = request.cost
    if cost is None:
        cost = RequestCost(request_id=request.id)
        request.cost = cost
    for field, value in asdict(breakdown).items():
        setattr(cost, field, value)
    cost.estimate_remark = remark
    cost.calculated_at = utc_now()
    cost.calculated_by = actor.id
    return cost


def cost_out(request: BookingRequest) -> CostBreakdownOut | None:
    cost = request.cost
    if cost is None:
        return None
    items = [
        CostItemOut(
            line_id=line.id,
            facility_name=line.facility_name_snapshot or line.facility.name,
            booking_date=line.booking_date,
            slot_label=line.slot_label_snapshot or line.slot.label,
            amount=float(line.line_amount_snapshot or 0),
        )
        for line in request.lines
        if line.decision == "CONFIRMED"
    ]
    intimated = cost.intimated_at is not None
    return CostBreakdownOut(
        items=items,
        booking_subtotal=float(cost.booking_subtotal),
        gst_pct=float(cost.gst_pct),
        gst_amount=float(cost.gst_amount),
        cleaning_pct=float(cost.cleaning_pct),
        cleaning_amount=float(cost.cleaning_amount),
        security_deposit=float(cost.security_deposit),
        electricity_estimate=float(cost.electricity_estimate),
        electricity_advance_pct=float(cost.electricity_advance_pct),
        electricity_advance=float(cost.electricity_advance),
        total_estimated_cost=float(cost.total_estimated_cost),
        advance_amount=float(cost.advance_amount),
        estimate_remark=cost.estimate_remark,
        calculated_at=cost.calculated_at,
        calculated_by_name=cost.calculator.name if cost.calculator is not None else None,
        intimated_at=cost.intimated_at,
        payment_url=cost.payment_url_snapshot if intimated else None,
        is_final=intimated,
    )
