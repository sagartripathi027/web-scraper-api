# app/schemas/scrape_schema.py
"""
Pydantic schemas used for request validation and response serialization.
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, HttpUrl, ConfigDict, field_validator


class ScrapeRequest(BaseModel):
    """Request body for POST /scrape and POST /scrape/background."""

    url: HttpUrl

    @field_validator("url")
    @classmethod
    def url_must_be_http_or_https(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme not in ("http", "https"):
            raise ValueError("URL scheme must be http or https")
        return value


class HeadingsSchema(BaseModel):
    """Structured representation of page headings."""

    h1: List[str] = []
    h2: List[str] = []
    h3: List[str] = []


class ScrapedContent(BaseModel):
    """Structured content extracted from a page (stored as JSON in DB)."""

    headings: HeadingsSchema
    paragraphs: List[str] = []
    links: List[str] = []
    images: List[str] = []


class ScrapedPageResponse(BaseModel):
    """Response schema representing a stored ScrapedPage row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[dict] = None
    keywords: Optional[List[str]] = None
    status: str
    created_at: datetime


class ScrapeResultResponse(BaseModel):
    """Response returned right after a scrape operation."""

    message: str
    data: ScrapedPageResponse


class BackgroundScrapeResponse(BaseModel):
    """Response returned immediately by POST /scrape/background."""

    message: str


class HealthResponse(BaseModel):
    """Response for GET /."""

    status: str
    app_name: str
    version: str