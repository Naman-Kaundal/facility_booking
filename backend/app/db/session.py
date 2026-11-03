"""Database engine/session setup and FastAPI dependencies."""

from collections.abc import Callable, Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings


def create_db_engine(url: str, connect_timeout: int = 5) -> Engine:
    # pool_pre_ping transparently replaces connections that PostgreSQL has closed.
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": connect_timeout})


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    engine = create_db_engine(settings.database_url, settings.database_connect_timeout)
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with request.app.state.session_factory() as session:
        yield session


def ping(session_factory: sessionmaker[Session]) -> bool:
    """Return True when the database answers ``SELECT 1``."""
    try:
        with session_factory() as session:
            session.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001 - any failure means "not reachable" for health purposes
        return False


def get_db_pinger(request: Request) -> Callable[[], bool]:
    """Dependency returning a zero-arg function that checks DB reachability (overridable in tests)."""
    factory = request.app.state.session_factory
    return lambda: ping(factory)
