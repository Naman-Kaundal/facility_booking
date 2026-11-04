"""Institute-wide cost settings and payment link (LLD §9.1, §10.10), stored in ``app_settings``.

Defaults come from the presentation's review/advance wireframe. Admins change them from the
admin page; a change only affects requests costed afterwards.
"""

from decimal import Decimal

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db.models import AppSettings

SETTINGS_ID = 1
DEFAULTS = {
    "gst_pct": Decimal("18"),
    "cleaning_pct": Decimal("10"),
    "security_deposit": 5000,
    "electricity_advance_pct": Decimal("80"),
    "payment_url": None,  # never invented: an admin must enter the institute's real payment page
}


def get(db: Session) -> AppSettings:
    """The settings row, creating it with the defaults if it's missing."""
    row = db.get(AppSettings, SETTINGS_ID)
    if row is None:
        db.execute(
            insert(AppSettings).values(id=SETTINGS_ID, **DEFAULTS).on_conflict_do_nothing(index_elements=["id"])
        )
        db.flush()
        row = db.get(AppSettings, SETTINGS_ID)
    return row


def payment_url_configured(db: Session) -> bool:
    return bool(get(db).payment_url)
