"""Sign-in with Google, sign-out, and an optional development-only sign-in."""

from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.deps import CSRF_HEADER, SESSION_COOKIE, get_app_settings
from app.api.users import me_out
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import constant_time_equals, new_token, sign, unsign
from app.db.session import get_db
from app.schemas.user import AuthConfigOut, DevLoginIn, MeOut
from app.services import auth_service
from app.services.google_oauth import GoogleOAuth

router = APIRouter(prefix="/auth", tags=["auth"])

OAUTH_COOKIE = "fb_oauth"
OAUTH_COOKIE_PATH = "/api/v1/auth"
OAUTH_MAX_AGE = 600  # the user has 10 minutes to finish signing in at Google


def get_google_oauth(settings: Settings = Depends(get_app_settings)) -> GoogleOAuth:
    return GoogleOAuth(settings)


def _frontend(settings: Settings, path: str, **params: str) -> str:
    query = f"?{urlencode(params)}" if params else ""
    return f"{settings.frontend_base_url}{path}{query}"


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,  # page scripts can't read it
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )


@router.get("/config", response_model=AuthConfigOut)
def auth_config(settings: Settings = Depends(get_app_settings)) -> AuthConfigOut:
    return AuthConfigOut(google_enabled=settings.google_configured, dev_login_enabled=settings.dev_login_allowed)


@router.get("/google")
def start_google_sign_in(
    settings: Settings = Depends(get_app_settings), google: GoogleOAuth = Depends(get_google_oauth)
) -> RedirectResponse:
    if not settings.google_configured:
        return RedirectResponse(_frontend(settings, "/login", error="GOOGLE_NOT_CONFIGURED"), status_code=302)

    state, nonce = new_token(), new_token()
    response = RedirectResponse(google.authorization_url(state, nonce), status_code=302)
    response.set_cookie(
        OAUTH_COOKIE,
        sign({"state": state, "nonce": nonce}, settings.app_secret_key, OAUTH_MAX_AGE),
        max_age=OAUTH_MAX_AGE,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",  # still sent on Google's top-level redirect back to us
        path=OAUTH_COOKIE_PATH,
    )
    return response


@router.get("/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
    google: GoogleOAuth = Depends(get_google_oauth),
) -> RedirectResponse:
    def fail(code_: str) -> RedirectResponse:
        response = RedirectResponse(_frontend(settings, "/login", error=code_), status_code=302)
        response.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
        return response

    if error:
        return fail("GOOGLE_CANCELLED")
    pending = unsign(request.cookies.get(OAUTH_COOKIE), settings.app_secret_key)
    # The state must match the one we issued to this browser (stops forged callbacks).
    if not code or pending is None or not constant_time_equals(state, pending.get("state")):
        return fail("INVALID_STATE")

    try:
        identity = google.exchange_code(code, pending["nonce"])
        user = auth_service.sign_in_user(
            db,
            sub=identity.sub,
            email=identity.email,
            name=identity.name,
            email_verified=identity.email_verified,
            iit_domain=settings.iit_email_domain,
        )
        token, _ = auth_service.create_session(db, user, settings.session_ttl_hours)
    except AppError as exc:
        db.rollback()
        return fail(exc.code)

    target = "/profile/category" if user.rate_category is None else "/home"
    response = RedirectResponse(_frontend(settings, target), status_code=302)
    response.delete_cookie(OAUTH_COOKIE, path=OAUTH_COOKIE_PATH)
    _set_session_cookie(response, token, settings)
    return response


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_app_settings)) -> Response:
    token = request.cookies.get(SESSION_COOKIE)
    session = auth_service.find_session(db, token)
    if session is not None and not constant_time_equals(request.headers.get(CSRF_HEADER), session.csrf_token):
        raise AppError("CSRF_FAILED", "Security check failed. Refresh the page and try again.", 403)
    auth_service.end_session(db, token)
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=settings.cookie_secure, samesite="lax")
    return response


@router.post("/dev-login", response_model=MeOut, include_in_schema=False)
def dev_login(
    body: DevLoginIn,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> MeOut:
    """Development only: sign in as any email without Google. Disabled unless DEV_LOGIN_ENABLED=true
    and APP_ENV is development/test, so it can never be switched on in production."""
    if not settings.dev_login_allowed:
        raise AppError("NOT_FOUND", "Not Found", 404)
    user = auth_service.sign_in_user(
        db,
        sub=f"dev:{body.email.lower()}",
        email=body.email,
        name=body.name or body.email.split("@")[0],
        email_verified=True,
        iit_domain=settings.iit_email_domain,
    )
    token, session = auth_service.create_session(db, user, settings.session_ttl_hours)
    _set_session_cookie(response, token, settings)
    return me_out(user, session, settings)
