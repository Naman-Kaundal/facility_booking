"""FastAPI application factory.

Run locally with:  uvicorn app.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session, sessionmaker

from app.api import auth, availability, facilities, health, requests, users, workflow
from app.core.config import INSECURE_DEFAULT_SECRET, Settings, get_settings
from app.core.errors import register_error_handlers
from app.db.session import create_session_factory

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None, session_factory: sessionmaker[Session] | None = None) -> FastAPI:
    """Build the app. Tests pass their own ``session_factory`` bound to the test database.

    The schema is created by Alembic migrations (`alembic upgrade head`), not at startup.
    """
    settings = settings or get_settings()
    if settings.app_env not in ("development", "test") and settings.app_secret_key == INSECURE_DEFAULT_SECRET:
        raise RuntimeError("Set APP_SECRET_KEY to a long random value outside development.")
    owns_engine = session_factory is None
    session_factory = session_factory or create_session_factory(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            if owns_engine:
                session_factory.kw["bind"].dispose()

    app = FastAPI(title=settings.app_name, version="0.4.0-week3", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(facilities.router, prefix=API_PREFIX)
    app.include_router(auth.router, prefix=API_PREFIX)
    app.include_router(users.router, prefix=API_PREFIX)
    app.include_router(requests.router, prefix=API_PREFIX)
    app.include_router(availability.router, prefix=API_PREFIX)
    app.include_router(workflow.router, prefix=API_PREFIX)
    return app


app = create_app()
