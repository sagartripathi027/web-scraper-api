# app/main.py
"""
FastAPI application entry point.

Defines all HTTP routes. Business logic lives in the service layer
(app/services/scraper_service.py) - routes here stay thin: validate
input, call the service, shape the response.
"""
from contextlib import asynccontextmanager
from typing import List

from fastapi import BackgroundTasks, FastAPI, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.connection import init_db, get_db
from app.scraper.extractor import (
    ScraperException,
    InvalidURLError,
    ScraperTimeoutError,
    ScraperConnectionError,
    ScraperHTTPError,
)
from app.schemas.scrape_schema import (
    ScrapeRequest,
    ScrapeResultResponse,
    ScrapedPageResponse,
    BackgroundScrapeResponse,
    HealthResponse,
)
from app.services.scraper_service import ScraperService, serialize_page, run_background_scrape


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Create database tables on application startup."""
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="A REST API that scrapes public websites and returns structured data.",
    lifespan=lifespan,
)


@app.get("/", response_model=HealthResponse, tags=["Health"])
def read_root() -> HealthResponse:
    """Basic health check / API status endpoint."""
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
    )


@app.post(
    "/scrape",
    response_model=ScrapeResultResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Scraper"],
)
def scrape_url(payload: ScrapeRequest, db: Session = Depends(get_db)) -> ScrapeResultResponse:
    """
    Scrape the given URL, clean and structure the extracted data,
    persist it to the database, and return the saved record.

    If the URL (normalized) was already scraped successfully before,
    the existing saved data is returned instead of scraping again.
    """
    service = ScraperService(db)
    try:
        page, is_duplicate = service.scrape_and_save(str(payload.url))

    except InvalidURLError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid URL: {exc}",
        )
    except ScraperTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Request timed out: {exc}",
        )
    except ScraperConnectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Website unavailable: {exc}",
        )
    except ScraperHTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Website returned an HTTP error: {exc}",
        )
    except ScraperException as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to scrape URL: {exc}",
        )
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors safely
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error while scraping: {exc}",
        )

    message = (
        "URL already scraped, returning existing data"
        if is_duplicate
        else "Page scraped and saved successfully"
    )

    return ScrapeResultResponse(
        message=message,
        data=ScrapedPageResponse(**serialize_page(page)),
    )


@app.post(
    "/scrape/background",
    response_model=BackgroundScrapeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Scraper"],
)
def scrape_url_background(
    payload: ScrapeRequest, background_tasks: BackgroundTasks
) -> BackgroundScrapeResponse:
    """
    Queue a scrape to run in the background and return immediately.

    The actual scrape -> clean -> persist workflow (including retries,
    duplicate detection, and error handling) runs after the response is
    sent, via run_background_scrape().
    """
    background_tasks.add_task(run_background_scrape, str(payload.url))
    return BackgroundScrapeResponse(message="Scraping task started")


@app.get("/pages", response_model=List[ScrapedPageResponse], tags=["Pages"])
def list_pages(db: Session = Depends(get_db)) -> List[ScrapedPageResponse]:
    """Return all scraped pages stored in the database."""
    service = ScraperService(db)
    pages = service.get_all_pages()
    return [ScrapedPageResponse(**serialize_page(p)) for p in pages]


@app.get("/pages/{page_id}", response_model=ScrapedPageResponse, tags=["Pages"])
def get_page(page_id: int, db: Session = Depends(get_db)) -> ScrapedPageResponse:
    """Return a single scraped page by its ID."""
    service = ScraperService(db)
    page = service.get_page_by_id(page_id)
    if not page:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No scraped page found with id={page_id}",
        )
    return ScrapedPageResponse(**serialize_page(page))


@app.get("/search", response_model=List[ScrapedPageResponse], tags=["Search"])
def search_pages(
    keyword: str = Query(..., min_length=1, description="Keyword to search for"),
    db: Session = Depends(get_db),
) -> List[ScrapedPageResponse]:
    """Search scraped pages whose extracted keywords match the given term."""
    service = ScraperService(db)
    matches = service.search_by_keyword(keyword)
    return [ScrapedPageResponse(**serialize_page(p)) for p in matches]