# app/database/connection.py
"""
Database connection and session management.

Sets up the SQLAlchemy engine, session factory, and declarative base.
Uses SQLite by default (configurable via DATABASE_URL in settings).
"""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config.settings import settings

# `check_same_thread` is required only for SQLite so that the connection
# can be shared across the threads FastAPI's threadpool may use.
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db() -> None:
    """Create all tables defined on Base's metadata (idempotent)."""
    # Import models here to ensure they are registered on Base.metadata
    from app.database import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_normalized_url_column()


def _ensure_normalized_url_column() -> None:
    """
    Lightweight auto-migration.

    Handles databases created before the `normalized_url` column existed:
    adds the column, backfills it from `url`, then adds the unique index.
    Safe to call on every startup - it's a no-op once the column already
    exists.
    """
    inspector = inspect(engine)
    if "scraped_pages" not in inspector.get_table_names():
        return

    existing_columns = {col["name"] for col in inspector.get_columns("scraped_pages")}
    if "normalized_url" in existing_columns:
        return

    from app.scraper.utils import normalize_stored_url

    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE scraped_pages ADD COLUMN normalized_url VARCHAR(2048)"))

        rows = conn.execute(text("SELECT id, url FROM scraped_pages")).fetchall()
        for row in rows:
            normalized = normalize_stored_url(row.url)
            conn.execute(
                text("UPDATE scraped_pages SET normalized_url = :normalized WHERE id = :id"),
                {"normalized": normalized, "id": row.id},
            )

        try:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_scraped_pages_normalized_url "
                    "ON scraped_pages (normalized_url)"
                )
            )
        except Exception:
            # Pre-existing duplicate URLs in old data would violate uniqueness.
            # Don't crash startup over it - dedupe those rows manually if this happens.
            pass


def get_db():
    """
    FastAPI dependency that yields a database session and
    guarantees it is closed after the request finishes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()