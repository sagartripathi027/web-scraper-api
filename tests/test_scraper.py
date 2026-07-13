"""
Basic pytest test-suite covering:
- Scraper utility / parsing functions
- API health check
- End-to-end /scrape flow using a mocked HTML fetch (no real network call)
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.scraper.parser import parse_html
from app.scraper.utils import (
    clean_text,
    remove_duplicates,
    remove_empty_values,
    extract_keywords,
)

@pytest.fixture(scope="module")
def client():
    """
    Yields a TestClient using a `with` block so FastAPI's lifespan
    (which creates the database tables) actually runs during tests.
    """
    with TestClient(app) as test_client:
        yield test_client

SAMPLE_HTML = """
<html>
    <head>
        <title>  Test Page Title  </title>
        <meta name="description" content="A sample page for testing." />
    </head>
    <body>
        <h1>Main Heading</h1>
        <h2>Sub Heading One</h2>
        <h2>Sub Heading One</h2>
        <p>This is a paragraph about python testing and python scraping.</p>
        <p></p>
        <a href="/about">About</a>
        <a href="https://example.com/contact">Contact</a>
        <img src="/images/logo.png" />
    </body>
</html>
"""


# ---------------------------------------------------------------------------
# Utility function tests
# ---------------------------------------------------------------------------

def test_clean_text_removes_extra_whitespace():
    assert clean_text("  hello   world  \n") == "hello world"


def test_remove_empty_values_filters_blanks():
    assert remove_empty_values(["a", "", "  ", "b"]) == ["a", "b"]


def test_remove_duplicates_preserves_order():
    assert remove_duplicates(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]


def test_extract_keywords_returns_frequent_words():
    text = "python python python testing scraping scraping"
    keywords = extract_keywords(text, top_n=2)
    assert keywords[0] == "python"
    assert "scraping" in keywords


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

def test_parse_html_extracts_expected_fields():
    result = parse_html(SAMPLE_HTML, base_url="https://example.com")

    assert result["title"] == "Test Page Title"
    assert result["description"] == "A sample page for testing."
    assert result["headings"]["h1"] == ["Main Heading"]
    assert result["headings"]["h2"] == ["Sub Heading One"]  # duplicate removed
    assert any("python testing" in p for p in result["paragraphs"])
    assert "https://example.com/about" in result["links"]
    assert "https://example.com/contact" in result["links"]
    assert "https://example.com/images/logo.png" in result["images"]


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------

def test_health_check(client):
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app_name" in body


def test_scrape_endpoint_with_mocked_fetch(client):
    """
    Mocks the network call so the test is fast, deterministic, and
    does not depend on external websites being reachable.
    """
    with patch("app.services.scraper_service.fetch_html", return_value=SAMPLE_HTML):
        response = client.post("/scrape", json={"url": "https://example.com"})

    assert response.status_code == 201
    body = response.json()
    assert body["data"]["title"] == "Test Page Title"
    assert "python" in body["data"]["keywords"]

    page_id = body["data"]["id"]

    # Fetch the same page back by ID
    get_response = client.get(f"/pages/{page_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == page_id


def test_get_nonexistent_page_returns_404(client):
    response = client.get("/pages/999999")
    assert response.status_code == 404


def test_search_endpoint_requires_keyword_param(client):
    response = client.get("/search")
    assert response.status_code == 422  # missing required query param
