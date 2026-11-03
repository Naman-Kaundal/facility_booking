"""Test fixtures backed by a real PostgreSQL test database.

The test database (TEST_DATABASE_URL, default ``facility_booking_test``) is created if
missing, migrated with Alembic once per test run, and wiped before every test.
Your development database is never touched.
"""

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.create_database import ensure_database
from app.db.seed import seed_all
from app.db.session import create_db_engine, get_db_pinger
from app.main import create_app
from app.services import roles_service
from app.services.auth_service import create_session, sign_in_user

BACKEND_DIR = Path(__file__).resolve().parent.parent
TABLES = (
    "reservations, status_events, reference_counters, staff_roles, request_lines, requests, sessions, users, "
    "slot_windows, tariffs, facility_slot_types, facilities"
)


def _test_database_url() -> str:
    return os.environ.get("TEST_DATABASE_URL") or Settings().test_database_url


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # configparser escaping
    return cfg


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = _test_database_url()
    name = make_url(url).database or ""
    if not name.endswith("_test"):
        pytest.exit(f"Refusing to run: test database name '{name}' must end with '_test' (tests wipe it).", 2)
    return url


@pytest.fixture(scope="session")
def engine(test_database_url):
    try:
        ensure_database(test_database_url)
    except OperationalError as exc:
        pytest.exit(
            "Cannot connect to PostgreSQL for tests. Is PostgreSQL running, and is the password in "
            f"TEST_DATABASE_URL (backend/.env) correct?\n{exc.orig}",
            2,
        )
    cfg = alembic_config(test_database_url)
    command.downgrade(cfg, "base")  # start from an empty schema every run
    command.upgrade(cfg, "head")
    eng = create_db_engine(test_database_url)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {TABLES} RESTART IDENTITY CASCADE"))
    return sessionmaker(bind=engine, expire_on_commit=False)


@pytest.fixture
def db(session_factory):
    with session_factory() as session:
        yield session


@pytest.fixture
def seeded_db(db):
    seed_all(db)
    return db


@pytest.fixture
def settings(test_database_url) -> Settings:
    return Settings(
        app_env="test",
        database_url=test_database_url,
        app_secret_key="test-secret",
        google_client_id="test-client-id.apps.googleusercontent.com",
        google_client_secret="test-client-secret",
        frontend_url="http://localhost:5173",
        dev_login_enabled=False,
    )


def _make_client(app):
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def client(settings, session_factory, seeded_db):
    app = create_app(settings=settings, session_factory=session_factory)
    async with _make_client(app) as http:
        yield http


@pytest.fixture
async def unhealthy_client(settings, session_factory):
    app = create_app(settings=settings, session_factory=session_factory)
    app.dependency_overrides[get_db_pinger] = lambda: (lambda: False)
    async with _make_client(app) as http:
        yield http


@pytest.fixture
async def offline_client(settings):
    """App pointed at a port where nothing listens, to exercise 'database down' handling."""
    dead = create_db_engine("postgresql+psycopg://nobody:nothing@127.0.0.1:1/nowhere", connect_timeout=1)
    app = create_app(settings=settings, session_factory=sessionmaker(bind=dead))
    async with _make_client(app) as http:
        yield http
    dead.dispose()


@pytest.fixture
def app(settings, session_factory, seeded_db):
    return create_app(settings=settings, session_factory=session_factory)


class SignedIn:
    """An HTTP client signed in as one user, sending the session cookie and CSRF header."""

    def __init__(self, http: AsyncClient, user_id: int, csrf_token: str) -> None:
        self.http = http
        self.user_id = user_id
        self.csrf_token = csrf_token

    def __getattr__(self, name):
        return getattr(self.http, name)


@pytest.fixture
async def sign_in(app, session_factory, settings):
    """Factory: ``await sign_in("someone@gmail.com", category="PRIVATE")`` -> SignedIn client."""
    opened: list[AsyncClient] = []

    async def _sign_in(
        email: str, category: str | None = "PRIVATE", name: str = "Test User", roles: tuple[str, ...] = ()
    ) -> SignedIn:
        with session_factory() as db:
            for role in roles:
                roles_service.grant(db, email, role, assigned_by="test")
            user = sign_in_user(
                db, sub=f"sub-{email}", email=email, name=name, email_verified=True,
                iit_domain=settings.iit_email_domain,
            )
            if category and user.rate_category is None:
                user.rate_category = category
            token, session = create_session(db, user, settings.session_ttl_hours)
            user_id, csrf = user.id, session.csrf_token
        http = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Cookie": f"fb_session={token}", "X-CSRF-Token": csrf},
        )
        opened.append(http)
        return SignedIn(http, user_id, csrf)

    yield _sign_in
    for http in opened:
        await http.aclose()
