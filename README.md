# Smart Web Scraper API

A production-style REST API, built with **FastAPI**, that scrapes public web
pages (no login/auth required) and returns clean, structured data: titles,
meta descriptions, headings, paragraphs, links, images, and auto-extracted
keywords. Every scrape is persisted to a database and searchable afterwards.

---

## Features

- 🔎 **Scraping engine** — `requests` + `BeautifulSoup4` with:
  - Custom `User-Agent` header
  - Configurable request timeout
  - Retry mechanism with backoff
  - Clear exception handling (bad status codes, timeouts, unreachable hosts, wrong content-type)
- 🧹 **Data cleaning**
  - Duplicate link/heading/paragraph removal
  - Empty-value stripping
  - Whitespace normalization
  - Simple frequency-based keyword extraction (stopword-filtered)
- 🗄️ **Persistence** — SQLAlchemy ORM models on SQLite (swappable via `DATABASE_URL`)
- 🌐 **REST API** — 5 endpoints covering scraping, listing, retrieval, and keyword search
- 🐳 **Dockerized** — one command to build and run
- ✅ **Tests** — pytest suite covering utils, parser, and API (including a mocked end-to-end scrape)
- 🏗️ **Clean architecture** — scraper / service / database / schema / API layers are fully separated

---

## Architecture (text diagram)

```
                        ┌─────────────────────────┐
                        │        Client           │
                        │ (curl / Postman / UI)    │
                        └────────────┬────────────┘
                                     │ HTTP
                                     ▼
                        ┌─────────────────────────┐
                        │      app/main.py         │   <- FastAPI routes (thin controllers)
                        │  /, /scrape, /pages,     │
                        │  /pages/{id}, /search    │
                        └────────────┬────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────┐
                    │  app/services/scraper_service.py │  <- Orchestration layer
                    │  scrape_and_save / get / search  │
                    └───────┬───────────────────┬──────┘
                            │                   │
              ┌─────────────▼───────┐   ┌───────▼─────────────┐
              │   app/scraper/       │   │  app/database/       │
              │  extractor.py        │   │  connection.py        │
              │   -> fetch_html()    │   │  models.py             │
              │  parser.py            │   │  -> SQLAlchemy engine  │
              │   -> parse_html()     │   │  -> ScrapedPage model  │
              │  utils.py              │   └───────────────────────┘
              │   -> clean/dedupe/     │
              │      keyword extract   │
              └────────────────────────┘
                            │
                            ▼
                 ┌───────────────────────┐
                 │   Target Website       │
                 │ (public, no login)     │
                 └───────────────────────┘

  app/schemas/scrape_schema.py  -> Pydantic request/response models (used by main.py)
  app/config/settings.py        -> Centralized environment-based configuration
```

**Folder structure:**

```
web-scraper-api/
│
├── app/
│   ├── main.py                    # FastAPI app & routes
│   ├── scraper/
│   │   ├── extractor.py           # HTTP fetching (requests, retries, timeouts)
│   │   ├── parser.py              # BeautifulSoup HTML parsing
│   │   └── utils.py               # Cleaning helpers + keyword extraction
│   ├── services/
│   │   └── scraper_service.py     # Orchestrates scrape -> clean -> persist
│   ├── database/
│   │   ├── connection.py          # SQLAlchemy engine/session/Base
│   │   └── models.py              # ScrapedPage ORM model
│   ├── schemas/
│   │   └── scrape_schema.py       # Pydantic request/response schemas
│   └── config/
│       └── settings.py            # Environment-based settings
│
├── tests/
│   └── test_scraper.py            # pytest suite
│
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
├── .dockerignore
└── README.md
```

---

## Installation (local, without Docker)

**Requirements:** Python 3.11+

```bash
# 1. Clone / unzip the project, then move into it
cd web-scraper-api

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the API (auto-reload during development)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at **http://localhost:8000**, with interactive
docs at **http://localhost:8000/docs** (Swagger) and **/redoc**.

The SQLite database file (`scraper.db`) is created automatically on startup
in the project root — no manual migration step needed.

---

## Running with Docker

```bash
docker-compose up --build
```

This will:
1. Build the image from the `Dockerfile`
2. Install all dependencies
3. Start the API on **http://localhost:8000**
4. Persist the SQLite database in a named Docker volume (`scraper_data`), so data survives container restarts

Stop it with:

```bash
docker-compose down
```

To rebuild after code changes:

```bash
docker-compose up --build --force-recreate
```

---

## Configuration

All configuration is read from environment variables / the `.env` file (see `app/config/settings.py`):

| Variable          | Default                                   | Description                              |
|-------------------|--------------------------------------------|-------------------------------------------|
| `APP_NAME`        | `Smart Web Scraper API`                   | Display name of the app                   |
| `APP_VERSION`     | `1.0.0`                                   | API version string                        |
| `DEBUG`           | `True`                                    | Debug flag                                |
| `DATABASE_URL`    | `sqlite:///./scraper.db`                  | SQLAlchemy database URL                   |
| `REQUEST_TIMEOUT` | `10`                                       | Per-request timeout (seconds)             |
| `MAX_RETRIES`     | `3`                                        | Retry attempts for failed fetches         |
| `USER_AGENT`      | (a modern Chrome UA string)                | User-Agent header sent with each request  |

---

## API Documentation

### `GET /`
Health check / API status.

**Response `200`:**
```json
{
  "status": "ok",
  "app_name": "Smart Web Scraper API",
  "version": "1.0.0"
}
```

---

### `POST /scrape`
Scrapes the given URL, cleans the extracted data, saves it, and returns the saved record.

**Request body:**
```json
{
  "url": "https://example.com"
}
```

**Response `201`:**
```json
{
  "message": "Page scraped and saved successfully",
  "data": {
    "id": 1,
    "url": "https://example.com",
    "title": "Example Domain",
    "description": "",
    "content": {
      "headings": { "h1": ["Example Domain"], "h2": [], "h3": [] },
      "paragraphs": ["This domain is for use in illustrative examples..."],
      "links": ["https://www.iana.org/domains/example"],
      "images": []
    },
    "keywords": ["example", "domain", "illustrative"],
    "status": "success",
    "created_at": "2026-07-13T09:50:54.367611"
  }
}
```

**Error responses:**
- `502 Bad Gateway` — the target site could not be reached after retries
- `422 Unprocessable Entity` — invalid/malformed URL in the request body
- `500 Internal Server Error` — unexpected server-side error

---

### `GET /pages`
Returns all scraped pages (most recent first).

**Response `200`:** array of page objects (same shape as `data` above).

---

### `GET /pages/{id}`
Returns a single scraped page by its database ID.

**Response `200`:** a single page object.
**Response `404`:** if no page exists with that ID.

---

### `GET /search?keyword=python`
Searches previously scraped pages whose extracted **keywords** contain the given term (case-insensitive substring match).

**Response `200`:** array of matching page objects (possibly empty).

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite covers:
- Utility functions (`clean_text`, `remove_duplicates`, `remove_empty_values`, `extract_keywords`)
- HTML parsing (`parse_html`) against sample HTML
- API health check (`GET /`)
- Full `/scrape` flow with the network call mocked (fast, deterministic, no external dependency)
- `404` handling for a non-existent page
- `422` validation for a missing required query parameter

---

## Notes & Design Decisions

- **Layered architecture:** `main.py` (routes) → `scraper_service.py` (orchestration) → `extractor.py` / `parser.py` (scraping) / `models.py` (persistence). Each layer only knows about the one below it, which keeps the codebase testable and easy to extend (e.g., swapping SQLite for PostgreSQL only touches `connection.py`/`.env`).
- **Failed scrapes are still recorded** (`status="failed"`) so failures are auditable via `/pages`, while the API still returns a `502` to the caller.
- **Keyword extraction** is a simple frequency-based approach (stopword-filtered word counting) — sufficient for lightweight tagging/search without pulling in an NLP dependency.
- This project only scrapes **public pages that don't require login**, and is intended for educational / internal-tooling use. Always respect a site's `robots.txt` and Terms of Service before scraping in production.
