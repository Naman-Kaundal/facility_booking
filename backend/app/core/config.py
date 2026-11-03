"""Application configuration loaded from environment variables (and an optional .env file)."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development")
    app_name: str = Field(default="IIT Ropar Facility Booking")
    # Signs the short-lived OAuth state cookie. Must be a long random value outside development.
    app_secret_key: str = Field(default=INSECURE_DEFAULT_SECRET)

    # SQLAlchemy URL. Format: postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/facility_booking")
    # Separate database used by pytest. Its name must end in "_test" (tests wipe it).
    test_database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/facility_booking_test"
    )
    # Seconds to wait for PostgreSQL before reporting it as unreachable.
    database_connect_timeout: int = Field(default=5, ge=1)

    # Comma-separated list of browser origins allowed to call the API. The first one is
    # where the browser is sent after signing in.
    frontend_url: str = Field(default="http://localhost:5173")

    # Google OAuth (Week 2). Create a "Web application" client in Google Cloud Console.
    google_client_id: str = Field(default="")
    google_client_secret: str = Field(default="")
    google_redirect_uri: str = Field(default="http://localhost:8000/api/v1/auth/callback")

    # Accounts with exactly this email domain get the IIT rate category automatically.
    iit_email_domain: str = Field(default="iitrpr.ac.in")

    # Sign-in sessions
    session_ttl_hours: int = Field(default=168, ge=1)  # 7 days
    # Send cookies only over HTTPS. Must be true when deployed behind HTTPS.
    cookie_secure: bool = Field(default=False)

    # Development-only sign-in without Google, for testing when an account can't use the
    # OAuth app. Ignored unless APP_ENV is "development" or "test".
    dev_login_enabled: bool = Field(default=False)

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_url.split(",") if origin.strip()]

    @property
    def frontend_base_url(self) -> str:
        origins = self.cors_origins
        return origins[0].rstrip("/") if origins else "http://localhost:5173"

    @property
    def google_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def dev_login_allowed(self) -> bool:
        return self.dev_login_enabled and self.app_env in ("development", "test")


@lru_cache
def get_settings() -> Settings:
    return Settings()
