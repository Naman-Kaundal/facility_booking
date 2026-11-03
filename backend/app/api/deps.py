"""Shared FastAPI dependencies: settings, the signed-in user, and CSRF protection."""

from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import constant_time_equals
from app.db.models import User, UserSession
from app.db.session import get_db
from app.services import roles_service
from app.services.auth_service import find_session

SESSION_COOKIE = "fb_session"
CSRF_HEADER = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def get_app_settings(request: Request) -> Settings:
    """The settings this app instance was created with (not the global .env defaults)."""
    return request.app.state.settings


def get_current_session(request: Request, db: Session = Depends(get_db)) -> UserSession:
    """401 unless the request carries a valid session cookie.

    For state-changing requests the X-CSRF-Token header must also match the session's
    token. A malicious site can make the browser send our cookie, but cannot read the
    token, so it cannot forge the header.
    """
    session = find_session(db, request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise AppError("UNAUTHENTICATED", "Please sign in.", 401)
    if request.method in UNSAFE_METHODS and not constant_time_equals(
        request.headers.get(CSRF_HEADER), session.csrf_token
    ):
        raise AppError("CSRF_FAILED", "Security check failed. Refresh the page and try again.", 403)
    return session


def get_current_user(session: UserSession = Depends(get_current_session)) -> User:
    return session.user


@dataclass
class StaffContext:
    user: User
    roles: list[str]


def require_role(*allowed: str) -> Callable[..., StaffContext]:
    """Dependency factory: 403 unless the signed-in user has an active role in ``allowed``.

    Hiding a button in the browser is not security; every desk endpoint uses this check.
    """

    def dependency(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> StaffContext:
        roles = roles_service.active_roles(db, user.email)
        if not set(roles) & set(allowed):
            raise AppError("FORBIDDEN", "You don't have access to this desk.", 403, {"required": list(allowed)})
        return StaffContext(user=user, roles=roles)

    return dependency
