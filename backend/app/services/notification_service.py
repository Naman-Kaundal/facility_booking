"""Workflow email notifications with a delivery log (LLD §14).

1. While a workflow action runs, ``notify_*`` writes one PENDING row per recipient to
   ``email_logs`` in the same transaction as the action. If the action fails, no email exists.
2. After the action is committed, ``send_queued()`` tries to deliver those rows and records
   SENT or FAILED (with the error) and the attempt count. A failed email never undoes the action.
3. Failed or stuck emails are retried later, up to ``EMAIL_MAX_ATTEMPTS`` tries each, by
   ``python -m app.db.retry_emails`` or the admin page.

Duplicates are prevented by ``idempotency_key`` = event + the audit event that caused it +
recipient, so retrying an API call or refreshing a page never sends the same email twice.
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models import BookingRequest, EmailLog, StatusEvent
from app.services import email_templates, roles_service
from app.services.email_sender import EmailSender, OutgoingEmail

logger = logging.getLogger("app.email")

DESK_FOR_ROLE = {"FACILITY": "FACILITY", "ACADEMIC": "ACADEMIC", "SPORTS": "SPORTS", "ESTATE": "ESTATE"}


@dataclass
class DeliveryReport:
    sent: int = 0
    failed: int = 0
    skipped: int = 0


class Notifier:
    def __init__(self, db: Session, sender: EmailSender, app_url: str, max_attempts: int = 3) -> None:
        self.db = db
        self.sender = sender
        self.app_url = app_url.rstrip("/")
        self.max_attempts = max_attempts
        self._queued: list[int] = []

    # ----- queueing (inside the workflow transaction) -----

    def notify_requester(self, request: BookingRequest, event: str, trigger: StatusEvent, note: str | None = None):
        self._queue(request, event, [request.contact_email], trigger, f"{self.app_url}/requests/{request.id}", note)

    def notify_role(
        self, role: str, request: BookingRequest, event: str, trigger: StatusEvent, note: str | None = None
    ) -> None:
        link = f"{self.app_url}/desk/requests/{request.id}?desk={DESK_FOR_ROLE.get(role, role)}"
        self._queue(request, event, roles_service.emails_with_role(self.db, role), trigger, link, note)

    def _queue(
        self,
        request: BookingRequest,
        event: str,
        recipients: Iterable[str],
        trigger: StatusEvent,
        link: str,
        note: str | None,
    ) -> None:
        unique = sorted({r.strip().lower() for r in recipients if r and r.strip()})
        if not unique:
            logger.info("No recipients for %s on request %s", event, request.id)
            return
        self.db.flush()  # gives the triggering audit event its id
        rendered = email_templates.render(event, request, link=link, note=note)
        for recipient in unique:
            stmt = (
                insert(EmailLog)
                .values(
                    request_id=request.id,
                    event=event,
                    recipient=recipient,
                    subject=rendered.subject,
                    body_text=rendered.text,
                    body_html=rendered.html,
                    status="PENDING",
                    attempt_count=0,
                    idempotency_key=f"{event}:{trigger.id}:{recipient}",
                )
                .on_conflict_do_nothing(constraint="uq_email_logs_idempotency_key")
                .returning(EmailLog.id)
            )
            new_id = self.db.execute(stmt).scalar()
            if new_id is not None:
                self._queued.append(new_id)

    # ----- delivery (after the workflow transaction is committed) -----

    def send_queued(self) -> DeliveryReport:
        ids, self._queued = self._queued, []
        return self.deliver(ids)

    def retry_failed(self, limit: int = 200) -> DeliveryReport:
        """Try again every FAILED (or never-attempted PENDING) email that has tries left."""
        ids = self.db.scalars(
            select(EmailLog.id)
            .where(
                or_(EmailLog.status == "FAILED", EmailLog.status == "PENDING"),
                EmailLog.attempt_count < self.max_attempts,
            )
            .order_by(EmailLog.created_at, EmailLog.id)
            .limit(limit)
        ).all()
        return self.deliver(list(ids))

    def deliver(self, ids: list[int]) -> DeliveryReport:
        report = DeliveryReport()
        for email_id in ids:
            row = self.db.get(EmailLog, email_id)
            if row is None or row.status == "SENT" or row.attempt_count >= self.max_attempts:
                report.skipped += 1
                continue
            row.attempt_count += 1
            row.last_attempt_at = utc_now()
            try:
                row.provider_message_id = self.sender.send(
                    OutgoingEmail(to=row.recipient, subject=row.subject, text=row.body_text, html=row.body_html)
                )
                row.status = "SENT"
                row.sent_at = utc_now()
                row.last_error = None
                report.sent += 1
            except Exception as exc:  # any delivery problem is recorded, never raised to the user
                row.status = "FAILED"
                row.last_error = f"{type(exc).__name__}: {exc}"[:1000]
                report.failed += 1
                logger.warning("Email %s to %s failed (attempt %s): %s", row.id, row.recipient, row.attempt_count, exc)
            self.db.commit()
        return report
