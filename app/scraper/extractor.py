# app/scraper/extractor.py
"""
HTTP fetching layer (the "extractor").

Responsible ONLY for fetching raw HTML from a target URL. Parsing/data
extraction from HTML is handled separately in parser.py, keeping this
module focused on network concerns: headers, timeouts, retries, errors.

Production-hardening added:
- requests.Session + HTTPAdapter + urllib3 Retry for automatic retries
  with backoff on transient failures (429, 500, 502, 503, 504).
- Separate connect/read timeouts.
- Specific, catchable exception types for invalid URLs, timeouts,
  connection failures and HTTP errors, so the API layer can return
  clean JSON error responses instead of crashing.
"""
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import (
    ConnectionError as RequestsConnectionError,
    ConnectTimeout,
    HTTPError,
    InvalidSchema,
    InvalidURL as RequestsInvalidURL,
    MissingSchema,
    ReadTimeout,
    RequestException,
    Timeout,
)
from urllib3.util.retry import Retry

from app.config.settings import settings
from app.scraper.utils import is_valid_url


class ScraperException(Exception):
    """Base exception raised when a page cannot be fetched."""


class InvalidURLError(ScraperException):
    """Raised when the provided URL is malformed or invalid."""


class ScraperTimeoutError(ScraperException):
    """Raised when the request times out (connect or read) after all retries."""


class ScraperConnectionError(ScraperException):
    """Raised when the target website is unreachable/unavailable."""


class ScraperHTTPError(ScraperException):
    """Raised when the target site returns a non-retryable HTTP error status."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """
    Build (once) and reuse a requests.Session configured with an
    HTTPAdapter + urllib3 Retry strategy so transient failures are
    retried automatically with backoff before we ever see them.
    """
    global _session
    if _session is not None:
        return _session

    retry_strategy = Retry(
        total=settings.max_retries,
        status_forcelist=settings.retry_status_codes,
        backoff_factor=settings.backoff_factor,
        allowed_methods=frozenset(["GET", "HEAD"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)

    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    _session = session
    return session


def fetch_html(url: str) -> str:
    """
    Fetch the raw HTML content of a URL.

    Applies:
    - Custom User-Agent header (some sites block default python-requests UA)
    - Separate connect/read timeouts
    - Automatic retry-with-backoff for status codes 429, 500, 502, 503, 504

    Raises:
        InvalidURLError: if the URL is malformed or invalid.
        ScraperTimeoutError: if the request times out after retries.
        ScraperConnectionError: if the website cannot be reached (down/unavailable).
        ScraperHTTPError: if the site returns a non-retryable HTTP error.
        ScraperException: for any other unexpected fetch failure.
    """
    if not is_valid_url(url):
        raise InvalidURLError(f"'{url}' is not a valid http/https URL")

    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    session = _get_session()

    try:
        response = session.get(
            url,
            headers=headers,
            timeout=(settings.connect_timeout, settings.read_timeout),
        )
    except (MissingSchema, InvalidSchema, RequestsInvalidURL) as exc:
        raise InvalidURLError(f"Invalid URL '{url}': {exc}") from exc
    except ConnectTimeout as exc:
        raise ScraperTimeoutError(f"Connection to '{url}' timed out: {exc}") from exc
    except ReadTimeout as exc:
        raise ScraperTimeoutError(f"Reading response from '{url}' timed out: {exc}") from exc
    except Timeout as exc:
        raise ScraperTimeoutError(f"Request to '{url}' timed out: {exc}") from exc
    except RequestsConnectionError as exc:
        raise ScraperConnectionError(
            f"Could not connect to '{url}' - website unavailable: {exc}"
        ) from exc
    except RequestException as exc:
        raise ScraperException(f"Request to '{url}' failed: {exc}") from exc

    try:
        response.raise_for_status()
    except HTTPError as exc:
        raise ScraperHTTPError(
            f"'{url}' returned HTTP {response.status_code}",
            status_code=response.status_code,
        ) from exc

    content_type = response.headers.get("Content-Type", "")
    if "text/html" not in content_type and "xml" not in content_type:
        raise ScraperException(
            f"Unsupported content type for scraping: {content_type or 'unknown'}"
        )

    return response.text