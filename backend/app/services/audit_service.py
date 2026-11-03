"""Audit trail: every workflow action is written to the append-only status_events table."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import BookingRequest, RequestLine, StatusEvent, User
from app.schemas.request import TimelineEventOut

# Human-readable labels shown on the timeline.
EVENT_LABELS = {
    "SUBMITTED": "Request submitted",
    "RESUBMITTED": "Corrected request resubmitted",
    "RETURNED": "Returned for correction",
    "FORWARDED": "Forwarded to section(s)",
    "LINE_CONFIRMED": "Facility confirmed",
    "LINE_REJECTED": "Facility rejected",
    "STATUS_CHANGED": "Status changed",
}


def record(
    db: Session,
    request: BookingRequest,
    event_type: str,
    *,
    actor: User | None,
    role: str | None,
    from_status: str | None = None,
    to_status: str | None = None,
    remark: str | None = None,
    line: RequestLine | None = None,
) -> StatusEvent:
    """Add an event to the current transaction (committed together with the action itself)."""
    event = StatusEvent(
        request_id=request.id,
        request_line_id=line.id if line is not None else None,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        actor_id=actor.id if actor is not None else None,
        actor_role=role,
        remark=remark,
    )
    db.add(event)
    return event


def timeline(db: Session, request_id: int) -> list[TimelineEventOut]:
    events = db.scalars(
        select(StatusEvent)
        .where(StatusEvent.request_id == request_id)
        .order_by(StatusEvent.created_at, StatusEvent.id)
    ).all()
    out = []
    for e in events:
        line_text = None
        if e.line is not None:
            name = e.line.facility_name_snapshot or e.line.facility.name
            slot = e.line.slot_label_snapshot or e.line.slot.label
            line_text = f"{name}, {e.line.booking_date:%d %b %Y}, {slot}"
        out.append(
            TimelineEventOut(
                id=e.id,
                event_type=e.event_type,
                label=EVENT_LABELS.get(e.event_type, e.event_type.replace("_", " ").title()),
                from_status=e.from_status,
                to_status=e.to_status,
                actor_name=e.actor.name if e.actor is not None else "System",
                actor_role=e.actor_role,
                remark=e.remark,
                line=line_text,
                created_at=e.created_at,
            )
        )
    return out
