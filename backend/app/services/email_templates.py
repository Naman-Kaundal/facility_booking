"""Text and HTML bodies for workflow emails (LLD §14).

Each email names the reference number, the event, the facilities with dates and slots, the
current status and a link back to the app. No secrets or unnecessary personal data.
"""

from dataclasses import dataclass
from decimal import Decimal
from html import escape

from app.db.models import BookingRequest

STATUS_TEXT = {
    "SUBMITTED": "Submitted, waiting for Facilities",
    "RETURNED": "Returned for correction",
    "WITH_SECTION": "With the section(s)",
    "REJECTED": "Rejected",
    "WITH_ESTATE": "Waiting for Estate's electricity estimate",
    "COSTED": "Costed, waiting for Facilities",
    "ADVANCE_INTIMATED": "Advance intimated, waiting for payment",
}
DECISION_TEXT = {"PENDING": "awaiting decision", "CONFIRMED": "confirmed", "REJECTED": "rejected"}

# event -> (subject, opening sentence). {ref} is the reference number.
EVENTS: dict[str, tuple[str, str]] = {
    "REQUEST_SUBMITTED": (
        "Request {ref} received",
        "We have received your facility booking request. The Facilities Section will check it next.",
    ),
    "FACILITY_REVIEW_REQUIRED": (
        "New request {ref} to review",
        "A facility booking request is waiting on the Facilities desk.",
    ),
    "REQUEST_RETURNED": (
        "Request {ref} returned for correction",
        "The Facilities Section has returned your request. Please make the changes below and submit it again.",
    ),
    "REQUEST_FORWARDED": (
        "Request {ref} sent to the sections",
        "The Facilities Section has checked your request and sent it to the section(s) that decide on each "
        "facility.",
    ),
    "SECTION_ACTION_REQUIRED": (
        "Request {ref}: facilities to confirm or reject",
        "A request has facilities for your section to confirm or reject.",
    ),
    "SECTION_DECIDED": (
        "Request {ref}: a facility has been decided",
        "A section has made a decision on one of the facilities in this request.",
    ),
    "REQUEST_REJECTED": (
        "Request {ref} could not be approved",
        "Unfortunately none of the facilities in your request could be approved.",
    ),
    "ESTATE_ACTION_REQUIRED": (
        "Request {ref}: electricity estimate needed",
        "All sections have decided on this request. Please enter the approximate electricity charge.",
    ),
    "COST_READY": (
        "Request {ref}: costs ready to review",
        "Estate has entered the electricity estimate and the costs have been calculated. Please review them "
        "and send the advance intimation.",
    ),
    "ADVANCE_INTIMATED": (
        "Request {ref}: advance payment details",
        "Your booking has been costed. Please pay the advance below through the institute's payment page to "
        "complete the booking.",
    ),
}


@dataclass(frozen=True)
class Rendered:
    subject: str
    text: str
    html: str


def _inr(value) -> str:
    return f"₹{value:,.2f}"


def _pct(value) -> str:
    return f"{Decimal(value).normalize():f}"


def _lines(request: BookingRequest, show_decisions: bool) -> list[str]:
    out = []
    for line in request.lines:
        name = line.facility_name_snapshot or line.facility.name
        slot = line.slot_label_snapshot or line.slot.label
        text = f"{name}, {line.booking_date:%a %d %b %Y}, {slot}"
        if show_decisions:
            text += f" ({DECISION_TEXT.get(line.decision, line.decision.lower())})"
        out.append(text)
    return out


def _cost_rows(request: BookingRequest) -> list[tuple[str, str]]:
    cost = request.cost
    if cost is None:
        return []
    return [
        ("Booking charges (confirmed facilities)", _inr(cost.booking_subtotal)),
        (f"GST ({_pct(cost.gst_pct)}%)", _inr(cost.gst_amount)),
        (f"Cleaning ({_pct(cost.cleaning_pct)}%)", _inr(cost.cleaning_amount)),
        ("Security deposit (refundable)", _inr(cost.security_deposit)),
        ("Electricity (approximate)", _inr(cost.electricity_estimate)),
        (f"Electricity in advance ({_pct(cost.electricity_advance_pct)}%)", _inr(cost.electricity_advance)),
        ("Total estimated cost", _inr(cost.total_estimated_cost)),
        ("ADVANCE TO PAY NOW", _inr(cost.advance_amount)),
    ]


def render(event: str, request: BookingRequest, *, link: str, note: str | None = None) -> Rendered:
    subject_tpl, intro = EVENTS[event]
    ref = request.ref_no or f"#{request.id}"
    subject = f"[Facility Booking] {subject_tpl.format(ref=ref)}"
    show_decisions = request.status not in ("SUBMITTED", "RETURNED")
    lines = _lines(request, show_decisions)
    costs = _cost_rows(request) if event in ("ADVANCE_INTIMATED", "COST_READY") else []
    payment_url = request.cost.payment_url_snapshot if (event == "ADVANCE_INTIMATED" and request.cost) else None
    status = STATUS_TEXT.get(request.status, request.status)

    text = [intro, ""]
    if note:
        text += [note, ""]
    text += [f"Reference: {ref}", f"Event: {request.purpose}", f"Status: {status}", "", "Facilities:"]
    text += [f"  - {line}" for line in lines]
    if costs:
        text += ["", "Cost breakdown:"] + [f"  {label}: {value}" for label, value in costs]
    if payment_url:
        text += ["", f"Pay the advance here: {payment_url}", "Quote the reference number when you pay."]
    text += ["", f"Open the request: {link}", "", "Facilities Section, IIT Ropar (automated message)"]

    html = [f"<p>{escape(intro)}</p>"]
    if note:
        html.append(f"<p><strong>{escape(note)}</strong></p>")
    html.append(
        "<p>"
        f"<strong>Reference:</strong> {escape(ref)}<br>"
        f"<strong>Event:</strong> {escape(request.purpose)}<br>"
        f"<strong>Status:</strong> {escape(status)}"
        "</p>"
    )
    html.append("<ul>" + "".join(f"<li>{escape(line)}</li>" for line in lines) + "</ul>")
    if costs:
        rows = "".join(
            f"<tr><td>{escape(label)}</td><td style='text-align:right'>{escape(value)}</td></tr>"
            for label, value in costs
        )
        html.append(f"<table cellpadding='4'>{rows}</table>")
    if payment_url:
        html.append(
            f"<p><a href='{escape(payment_url, quote=True)}'>Pay the advance</a> "
            "(quote the reference number when you pay).</p>"
        )
    html.append(f"<p><a href='{escape(link, quote=True)}'>Open the request</a></p>")
    html.append("<p style='color:#666'>Facilities Section, IIT Ropar (automated message)</p>")

    return Rendered(subject=subject, text="\n".join(text), html="\n".join(html))
