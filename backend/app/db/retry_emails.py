"""Retry notification emails that failed (or were never attempted), up to EMAIL_MAX_ATTEMPTS each.

Usage:
    python -m app.db.retry_emails          # retry, then print what happened
    python -m app.db.retry_emails --list   # show the last 20 emails and their status

Safe to run any time (for example every few minutes from Windows Task Scheduler or cron):
emails that were already sent are never sent again.
"""

import argparse

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import EmailLog
from app.db.session import create_session_factory
from app.services.email_sender import build_sender
from app.services.notification_service import Notifier


def main() -> None:
    parser = argparse.ArgumentParser(description="Retry failed notification emails.")
    parser.add_argument("--list", action="store_true", help="Show the latest emails instead of retrying")
    args = parser.parse_args()

    settings = get_settings()
    factory = create_session_factory(settings)
    try:
        with factory() as db:
            if args.list:
                rows = db.scalars(select(EmailLog).order_by(EmailLog.id.desc()).limit(20))
                for row in rows:
                    print(f"#{row.id:<5} {row.status:<8} tries={row.attempt_count} {row.recipient:<35} {row.subject}")
                return
            notifier = Notifier(db, build_sender(settings), settings.frontend_base_url, settings.email_max_attempts)
            report = notifier.retry_failed()
            print(f"Sent {report.sent}, failed {report.failed}, skipped {report.skipped}.")
    finally:
        factory.kw["bind"].dispose()


if __name__ == "__main__":
    main()
