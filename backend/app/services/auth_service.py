"""Users, rate categories and sign-in sessions."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_token, new_token
from app.core.time import utc_now
from app.db.models import User, UserSession

EXTERNAL_CATEGORIES = ("GOVT", "PRIVATE")


def is_iit_email(email: str, domain: str) -> bool:
    """Exact domain match: 'a@iitrpr.ac.in' yes; 'a@notiitrpr.ac.in' and 'a@x.iitrpr.ac.in' no."""
    local, sep, host = email.strip().lower().rpartition("@")
    return bool(local) and sep == "@" and host == domain.lower()


def sign_in_user(db: Session, *, sub: str, email: str, name: str, email_verified: bool, iit_domain: str) -> User:
    """Create or update the user for a verified identity and apply the IIT email rule."""
    if not email_verified or not email:
        raise AppError("EMAIL_NOT_VERIFIED", "Your Google account's email address is not verified.", 403)
    email = email.strip().lower()

    user = db.scalar(select(User).where(User.google_sub == sub))
    if user is None:
        # Same verified email signing in with a new account id (e.g. dev login first): link it.
        user = db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.google_sub = sub
    if user is None:
        user = User(google_sub=sub, email=email, name=name or email)
        db.add(user)

    user.email = email
    user.name = name or user.name or email
    user.last_login_at = utc_now()
    if is_iit_email(email, iit_domain):
        user.rate_category = "IIT"
    elif user.rate_category == "IIT":
        user.rate_category = None  # no longer an institute address: must choose again
    db.flush()
    return user


def set_external_category(db: Session, user: User, category: str, iit_domain: str) -> User:
    if is_iit_email(user.email, iit_domain):
        raise AppError("CATEGORY_LOCKED", "IIT Ropar accounts always use the IIT rate.", 403)
    if category not in EXTERNAL_CATEGORIES:
        raise AppError("INVALID_CATEGORY", "Choose GOVT or PRIVATE.", 422)
    user.rate_category = category
    db.commit()
    return user


def create_session(db: Session, user: User, ttl_hours: int) -> tuple[str, UserSession]:
    """Return the raw token (for the cookie) and the stored session row."""
    token = new_token()
    session = UserSession(
        user_id=user.id,
        token_hash=hash_token(token),
        csrf_token=new_token(24),
        expires_at=utc_now() + timedelta(hours=ttl_hours),
    )
    db.add(session)
    db.commit()
    return token, session


def find_session(db: Session, token: str | None) -> UserSession | None:
    if not token:
        return None
    session = db.scalar(select(UserSession).where(UserSession.token_hash == hash_token(token)))
    if session is None or session.expires_at <= utc_now():
        return None
    return session


def end_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(UserSession).where(UserSession.token_hash == hash_token(token)))
        db.commit()
