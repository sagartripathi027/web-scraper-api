# app/database/models.py
"""
SQLAlchemy ORM models.
"""
from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, Index

from app.database.connection import Base


class ScrapedPage(Base):
    """Represents a single scraped web page and its extracted data."""

    __tablename__ = "scraped_pages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    url = Column(String(2048), nullable=False, index=True)

    # Normalized form of `url` (trailing slash / case differences resolved).
    # Used for fast, reliable duplicate-URL detection.
    normalized_url = Column(String(2048), nullable=True, unique=True, index=True)

    title = Column(String(1024), nullable=True)
    description = Column(Text, nullable=True)
    content = Column(Text, nullable=True)      # JSON-encoded structured content
    keywords = Column(Text, nullable=True)     # JSON-encoded list of keywords
    status = Column(String(50), nullable=False, default="success")  # success | failed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_scraped_pages_normalized_url_status", "normalized_url", "status"),
    )