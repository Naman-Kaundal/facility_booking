"""Ways to deliver an email. The notification service logs every attempt in ``email_logs``.

- ConsoleEmailSender (default): writes the email to the server log. Nothing leaves the machine.
- SmtpEmailSender: sends through the SMTP server configured in ``backend/.env``.
Tests replace the sender with a fake that records messages (and can simulate failures).
"""

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import make_msgid
from typing import Protocol

from app.core.config import Settings

logger = logging.getLogger("app.email")


@dataclass(frozen=True)
class OutgoingEmail:
    to: str
    subject: str
    text: str
    html: str


class EmailSender(Protocol):
    def send(self, message: OutgoingEmail) -> str | None:
        """Deliver the message or raise. Returns the provider's message id, if any."""


class ConsoleEmailSender:
    def send(self, message: OutgoingEmail) -> str | None:
        logger.info("EMAIL to=%s subject=%r\n%s", message.to, message.subject, message.text)
        return None


class SmtpEmailSender:
    def __init__(
        self, host: str, port: int, username: str, password: str, starttls: bool, from_addr: str, timeout: int = 15
    ) -> None:
        self.host, self.port, self.username, self.password = host, port, username, password
        self.starttls, self.from_addr, self.timeout = starttls, from_addr, timeout

    def send(self, message: OutgoingEmail) -> str | None:
        msg = EmailMessage()
        msg["From"] = self.from_addr
        msg["To"] = message.to
        msg["Subject"] = message.subject
        msg["Message-ID"] = make_msgid(domain=self.from_addr.rpartition("@")[2] or None)
        msg.set_content(message.text)
        msg.add_alternative(message.html, subtype="html")
        with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as smtp:
            if self.starttls:
                smtp.starttls()
            if self.username:
                smtp.login(self.username, self.password)
            smtp.send_message(msg)
        return msg["Message-ID"]


def build_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "smtp":
        if not settings.smtp_host:
            raise RuntimeError("EMAIL_BACKEND=smtp needs SMTP_HOST in backend/.env.")
        return SmtpEmailSender(
            settings.smtp_host,
            settings.smtp_port,
            settings.smtp_username,
            settings.smtp_password,
            settings.smtp_starttls,
            settings.email_from,
        )
    return ConsoleEmailSender()
