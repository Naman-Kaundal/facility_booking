"""Google sign-in flow, sessions, CSRF and the IIT email rule.

Google itself is replaced by a fake, so these tests check our side of the flow:
state checking, the identity rules, session cookies and redirects.
"""

from urllib.parse import parse_qs, urlparse

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.auth import get_google_oauth
from app.core.config import INSECURE_DEFAULT_SECRET
from app.core.errors import AppError
from app.main import create_app
from app.services.auth_service import is_iit_email
from app.services.google_oauth import GoogleIdentity, GoogleOAuth


class FakeGoogle(GoogleOAuth):
    def __init__(self, settings, identity: GoogleIdentity | None = None, error: str | None = None):
        super().__init__(settings)
        self.identity = identity
        self.error = error
        self.seen_nonce: str | None = None

    def exchange_code(self, code: str, nonce: str) -> GoogleIdentity:
        self.seen_nonce = nonce
        if self.error:
            raise AppError(self.error, "fake failure", 401)
        return self.identity


@pytest.fixture
def google_app(settings, session_factory, seeded_db):
    def make(identity: GoogleIdentity | None = None, error: str | None = None, **overrides):
        app = create_app(settings=settings.model_copy(update=overrides), session_factory=session_factory)
        fake = FakeGoogle(app.state.settings, identity, error)
        app.dependency_overrides[get_google_oauth] = lambda: fake
        return app, fake

    return make


def _client(app) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def identity(email: str, verified: bool = True, sub: str | None = None) -> GoogleIdentity:
    return GoogleIdentity(sub=sub or f"google-{email}", email=email, email_verified=verified, name="Asha Rao")


async def _full_sign_in(http: AsyncClient):
    start = await http.get("/api/v1/auth/google")
    assert start.status_code == 302
    state = parse_qs(urlparse(start.headers["location"]).query)["state"][0]
    return await http.get("/api/v1/auth/callback", params={"code": "one-time-code", "state": state})


@pytest.mark.parametrize(
    ("email", "expected"),
    [
        ("student@iitrpr.ac.in", True),
        ("Prof.X@IITRPR.AC.IN", True),
        ("person@notiitrpr.ac.in", False),  # lookalike domain (LLD §4.1)
        ("person@cse.iitrpr.ac.in", False),  # subdomain is not the institute domain
        ("iitrpr.ac.in@gmail.com", False),
        ("person@iitrpr.ac.in.evil.com", False),
        ("@iitrpr.ac.in", False),
        ("no-at-sign", False),
    ],
)
def test_iit_email_rule_is_an_exact_domain_match(email, expected):
    assert is_iit_email(email, "iitrpr.ac.in") is expected


async def test_sign_in_start_redirects_to_google_with_state_and_nonce(google_app):
    app, _ = google_app()
    async with _client(app) as http:
        response = await http.get("/api/v1/auth/google")
    assert response.status_code == 302
    location = urlparse(response.headers["location"])
    query = parse_qs(location.query)
    assert location.netloc == "accounts.google.com"
    assert query["client_id"] == ["test-client-id.apps.googleusercontent.com"]
    assert query["redirect_uri"] == ["http://localhost:8000/api/v1/auth/callback"]
    assert query["scope"] == ["openid email profile"]
    assert query["state"][0] and query["nonce"][0]
    assert "fb_oauth=" in response.headers["set-cookie"]
    assert "httponly" in response.headers["set-cookie"].lower()


async def test_iit_user_signs_in_and_skips_category_page(google_app):
    app, fake = google_app(identity("asha@iitrpr.ac.in"))
    async with _client(app) as http:
        response = await _full_sign_in(http)
        assert response.status_code == 302
        assert response.headers["location"] == "http://localhost:5173/home"
        assert fake.seen_nonce  # the nonce we issued was passed on for checking

        me = (await http.get("/api/v1/users/me")).json()
    assert me["email"] == "asha@iitrpr.ac.in"
    assert me["rate_category"] == "IIT"
    assert me["is_iit"] is True
    assert me["needs_category"] is False
    assert me["csrf_token"]


async def test_external_user_is_sent_to_category_page(google_app):
    app, _ = google_app(identity("someone@gmail.com"))
    async with _client(app) as http:
        response = await _full_sign_in(http)
        assert response.headers["location"] == "http://localhost:5173/profile/category"
        me = (await http.get("/api/v1/users/me")).json()
    assert me["rate_category"] is None
    assert me["needs_category"] is True


async def test_lookalike_domain_does_not_get_iit_rate(google_app):
    app, _ = google_app(identity("person@notiitrpr.ac.in"))
    async with _client(app) as http:
        await _full_sign_in(http)
        me = (await http.get("/api/v1/users/me")).json()
    assert me["rate_category"] is None
    assert me["is_iit"] is False


async def test_session_cookie_is_http_only(google_app):
    app, _ = google_app(identity("asha@iitrpr.ac.in"))
    async with _client(app) as http:
        response = await _full_sign_in(http)
    cookie = next(c for c in response.headers.get_list("set-cookie") if c.startswith("fb_session="))
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()


async def test_callback_without_matching_state_is_rejected(google_app):
    app, _ = google_app(identity("asha@iitrpr.ac.in"))
    async with _client(app) as http:
        await http.get("/api/v1/auth/google")
        response = await http.get("/api/v1/auth/callback", params={"code": "c", "state": "forged"})
        assert response.headers["location"] == "http://localhost:5173/login?error=INVALID_STATE"
        assert (await http.get("/api/v1/users/me")).status_code == 401


async def test_callback_without_oauth_cookie_is_rejected(google_app):
    app, _ = google_app(identity("asha@iitrpr.ac.in"))
    async with _client(app) as http:
        response = await http.get("/api/v1/auth/callback", params={"code": "c", "state": "anything"})
    assert response.headers["location"].endswith("/login?error=INVALID_STATE")


async def test_unverified_google_email_is_rejected(google_app):
    app, _ = google_app(identity("asha@iitrpr.ac.in", verified=False))
    async with _client(app) as http:
        response = await _full_sign_in(http)
    assert response.headers["location"].endswith("/login?error=EMAIL_NOT_VERIFIED")


async def test_failed_token_verification_redirects_with_error(google_app):
    app, _ = google_app(error="INVALID_ID_TOKEN")
    async with _client(app) as http:
        response = await _full_sign_in(http)
    assert response.headers["location"].endswith("/login?error=INVALID_ID_TOKEN")


async def test_user_cancelling_at_google_redirects_to_login(google_app):
    app, _ = google_app()
    async with _client(app) as http:
        response = await http.get("/api/v1/auth/callback", params={"error": "access_denied"})
    assert response.headers["location"].endswith("/login?error=GOOGLE_CANCELLED")


async def test_google_not_configured_redirects_with_error(google_app):
    app, _ = google_app(google_client_id="", google_client_secret="")
    async with _client(app) as http:
        response = await http.get("/api/v1/auth/google")
        config = (await http.get("/api/v1/auth/config")).json()
    assert response.headers["location"].endswith("/login?error=GOOGLE_NOT_CONFIGURED")
    assert config == {"google_enabled": False, "dev_login_enabled": False}


async def test_signing_in_again_reuses_the_same_user(google_app):
    app, _ = google_app(identity("asha@iitrpr.ac.in"))
    async with _client(app) as first, _client(app) as second:
        await _full_sign_in(first)
        await _full_sign_in(second)
        a = (await first.get("/api/v1/users/me")).json()
        b = (await second.get("/api/v1/users/me")).json()
    assert a["id"] == b["id"]
    assert a["csrf_token"] != b["csrf_token"]  # each browser gets its own session


async def test_protected_endpoints_need_a_session(client):
    for path in ("/api/v1/users/me", "/api/v1/requests"):
        response = await client.get(path)
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHENTICATED"


async def test_garbage_session_cookie_is_rejected(client):
    response = await client.get("/api/v1/users/me", headers={"Cookie": "fb_session=not-a-real-session"})
    assert response.status_code == 401


async def test_state_changing_request_without_csrf_header_is_rejected(sign_in):
    me = await sign_in("someone@gmail.com", category=None)
    response = await me.put(
        "/api/v1/users/me/rate-category", json={"rate_category": "GOVT"}, headers={"X-CSRF-Token": "wrong"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "CSRF_FAILED"


async def test_logout_ends_the_session(sign_in):
    me = await sign_in("someone@gmail.com")
    assert (await me.get("/api/v1/users/me")).status_code == 200
    response = await me.post("/api/v1/auth/logout")
    assert response.status_code == 204
    assert (await me.get("/api/v1/users/me")).status_code == 401


async def test_logout_requires_csrf(sign_in):
    me = await sign_in("someone@gmail.com")
    response = await me.post("/api/v1/auth/logout", headers={"X-CSRF-Token": "wrong"})
    assert response.status_code == 403
    assert (await me.get("/api/v1/users/me")).status_code == 200


async def test_dev_login_is_disabled_by_default(client):
    response = await client.post("/api/v1/auth/dev-login", json={"email": "a@iitrpr.ac.in"})
    assert response.status_code == 404


async def test_dev_login_is_never_available_in_production(google_app):
    app, _ = google_app(dev_login_enabled=True, app_env="production", app_secret_key="x" * 40)
    async with _client(app) as http:
        response = await http.post("/api/v1/auth/dev-login", json={"email": "a@iitrpr.ac.in"})
    assert response.status_code == 404


async def test_dev_login_applies_the_same_iit_rule(google_app):
    app, _ = google_app(dev_login_enabled=True)
    async with _client(app) as http:
        iit = await http.post("/api/v1/auth/dev-login", json={"email": "Asha@iitrpr.ac.in", "name": "Asha"})
        assert iit.status_code == 200
        assert iit.json()["rate_category"] == "IIT"
        assert (await http.get("/api/v1/users/me")).json()["email"] == "asha@iitrpr.ac.in"

    async with _client(app) as http:
        external = await http.post("/api/v1/auth/dev-login", json={"email": "x@notiitrpr.ac.in"})
    assert external.json()["rate_category"] is None


def test_production_refuses_the_default_secret(settings, session_factory):
    unsafe = settings.model_copy(update={"app_env": "production", "app_secret_key": INSECURE_DEFAULT_SECRET})
    with pytest.raises(RuntimeError, match="APP_SECRET_KEY"):
        create_app(settings=unsafe, session_factory=session_factory)
