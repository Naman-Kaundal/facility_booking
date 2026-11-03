"""Create the PostgreSQL database named in DATABASE_URL if it does not exist yet.

Run with:  python -m app.db.create_database
"""

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def ensure_database(url: str, connect_timeout: int = 5) -> bool:
    """Create the database in ``url`` if missing. Returns True if it was created."""
    target = make_url(url)
    name = target.database
    if not name:
        raise ValueError("DATABASE_URL must include a database name.")

    # Connect to the built-in "postgres" maintenance database to issue CREATE DATABASE.
    admin_url = target.set(database="postgres")
    engine = create_engine(
        admin_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": connect_timeout}
    )
    try:
        with engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": name}).first()
            if exists:
                return False
            quoted = conn.dialect.identifier_preparer.quote(name)
            conn.execute(text(f"CREATE DATABASE {quoted}"))
            return True
    finally:
        engine.dispose()


def _main() -> None:
    from app.core.config import get_settings

    url = get_settings().database_url
    name = make_url(url).database
    created = ensure_database(url)
    print(f"Database '{name}' {'created' if created else 'already exists'}.")


if __name__ == "__main__":
    _main()
