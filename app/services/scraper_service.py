# app/services/scraper_service.py
"""
Service layer: orchestrates the scraper (extractor + parser + data
cleaning) and persists results via SQLAlchemy. This is the layer the
API routes talk to - they should never touch scraping/parsing/DB
internals directly.
"""
import json
import logging
from typing import List, Optional, Tuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import ScrapedPage
from app.scraper.extractor import fetch_html, ScraperException
from app.scraper.parser import parse_html
from app.scraper.utils import (
    extract_keywords,
    remove_empty_values,
    remove_duplicates,
    normalize_stored_url,
)

logger = logging.getLogger(__name__)


class ScraperService:
    """Encapsulates the full scrape -> clean -> persist workflow."""

    def __init__(self, db: Session):
        self.db = db

    def scrape_and_save(self, url: str) -> Tuple[ScrapedPage, bool]:
        """
        Scrape the given URL, clean the extracted data, persist it, and
        return (page, is_duplicate).

        - If a page with the same normalized URL was already scraped
          successfully, that existing row is returned immediately and
          is_duplicate=True, with no network request made.
        - If a previous attempt for this URL failed, this call retries
          the scrape and updates that same row in place (so the unique
          constraint on normalized_url is respected).
        - If scraping fails, a row with status='failed' is still saved
          so failures are auditable, and the exception is re-raised for
          the API layer to translate into an HTTP error.
        """
        normalized = normalize_stored_url(url)

        existing = self._get_by_normalized_url(normalized)
        if existing and existing.status == "success":
            return existing, True

        try:
            html = fetch_html(url)
            parsed = parse_html(html, base_url=url)
            cleaned = self._clean_data(parsed)

            all_text = " ".join(
                cleaned["headings"]["h1"]
                + cleaned["headings"]["h2"]
                + cleaned["headings"]["h3"]
                + cleaned["paragraphs"]
            )
            keywords = extract_keywords(all_text, top_n=10)

            content_json = json.dumps(
                {
                    "headings": cleaned["headings"],
                    "paragraphs": cleaned["paragraphs"],
                    "links": cleaned["links"],
                    "images": cleaned["images"],
                }
            )
            keywords_json = json.dumps(keywords)

            if existing:  # previous failed attempt -> update in place
                existing.url = url
                existing.title = cleaned["title"] or None
                existing.description = cleaned["description"] or None
                existing.content = content_json
                existing.keywords = keywords_json
                existing.status = "success"
                page = existing
            else:
                page = ScrapedPage(
                    url=url,
                    normalized_url=normalized,
                    title=cleaned["title"] or None,
                    description=cleaned["description"] or None,
                    content=content_json,
                    keywords=keywords_json,
                    status="success",
                )

        except ScraperException as exc:
            if existing:  # previous failed attempt -> keep it as failed
                existing.url = url
                existing.title = None
                existing.description = None
                existing.content = None
                existing.keywords = json.dumps([])
                existing.status = "failed"
                page = existing
            else:
                page = ScrapedPage(
                    url=url,
                    normalized_url=normalized,
                    title=None,
                    description=None,
                    content=None,
                    keywords=json.dumps([]),
                    status="failed",
                )

            self._persist(page)
            raise exc

        self._persist(page)
        return page, False

    def _persist(self, page: ScrapedPage) -> None:
        """Add/commit a page, gracefully handling races on normalized_url."""
        try:
            self.db.add(page)
            self.db.commit()
            self.db.refresh(page)
        except IntegrityError:
            # Another request inserted the same normalized_url concurrently.
            # Roll back and fall back to whatever now exists in the DB.
            self.db.rollback()

    def _get_by_normalized_url(self, normalized_url: str) -> Optional[ScrapedPage]:
        """Look up a stored page by its normalized URL."""
        return (
            self.db.query(ScrapedPage)
            .filter(ScrapedPage.normalized_url == normalized_url)
            .first()
        )

    @staticmethod
    def _clean_data(parsed: dict) -> dict:
        """Apply data-cleaning rules: dedupe, strip empties/whitespace."""
        headings = {
            level: remove_duplicates(remove_empty_values(texts))
            for level, texts in parsed["headings"].items()
        }
        paragraphs = remove_duplicates(remove_empty_values(parsed["paragraphs"]))
        links = remove_duplicates(remove_empty_values(parsed["links"]))
        images = remove_duplicates(remove_empty_values(parsed["images"]))

        return {
            "title": parsed["title"],
            "description": parsed["description"],
            "headings": headings,
            "paragraphs": paragraphs,
            "links": links,
            "images": images,
        }

    def get_all_pages(self) -> List[ScrapedPage]:
        """Return all scraped pages, most recent first."""
        return self.db.query(ScrapedPage).order_by(ScrapedPage.created_at.desc()).all()

    def get_page_by_id(self, page_id: int) -> Optional[ScrapedPage]:
        """Return a single scraped page by its primary key, or None."""
        return self.db.query(ScrapedPage).filter(ScrapedPage.id == page_id).first()

    def search_by_keyword(self, keyword: str) -> List[ScrapedPage]:
        """
        Search stored pages whose `keywords` JSON field contains the
        given keyword (case-insensitive substring match).
        """
        keyword_lower = keyword.lower().strip()
        all_pages = self.db.query(ScrapedPage).order_by(ScrapedPage.created_at.desc()).all()

        matches = []
        for page in all_pages:
            page_keywords = json.loads(page.keywords) if page.keywords else []
            if any(keyword_lower in kw.lower() for kw in page_keywords):
                matches.append(page)
        return matches


def serialize_page(page: ScrapedPage) -> dict:
    """Convert a ScrapedPage ORM object into a JSON-serializable dict."""
    return {
        "id": page.id,
        "url": page.url,
        "title": page.title,
        "description": page.description,
        "content": json.loads(page.content) if page.content else None,
        "keywords": json.loads(page.keywords) if page.keywords else [],
        "status": page.status,
        "created_at": page.created_at,
    }


def run_background_scrape(url: str) -> None:
    """
    Entry point invoked by FastAPI BackgroundTasks.

    The request-scoped DB session is already closed by the time a
    background task runs, so this opens its own SessionLocal, performs
    the full scrape -> clean -> persist workflow via ScraperService,
    and always closes the session afterwards.

    Any error (scraper or unexpected) is logged and swallowed rather
    than raised - ScraperService already persists a status='failed'
    row for scraper errors, so the failure remains auditable in the
    database without crashing the background task runner.
    """
    db = SessionLocal()
    try:
        service = ScraperService(db)
        service.scrape_and_save(url)
    except ScraperException as exc:
        logger.warning("Background scrape failed for '%s': %s", url, exc)
    except Exception:  # noqa: BLE001 - never let a background task crash silently
        logger.exception("Unexpected error during background scrape of '%s'", url)
    finally:
        db.close()