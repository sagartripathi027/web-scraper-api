# app/config/settings.py
"""
Application configuration module.

Loads settings from environment variables / .env file using pydantic-settings.
Centralizing configuration here keeps the rest of the codebase free of
hard-coded values (timeouts, retries, DB credentials, etc.).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from environment variables."""

    # General app info
    app_name: str = "Smart Web Scraper API"
    app_version: str = "1.0.0"
    debug: bool = True

    # Full SQLAlchemy connection string actually used by the app.
    # Defaults to SQLite for local runs; docker-compose overrides it to Postgres.
    database_url: str = "sqlite:///./scraper.db"

    # Postgres credentials - declared explicitly so they're validated
    # (not just silently swallowed) whenever they appear in the environment.
    # Optional because they're irrelevant when running locally against SQLite.
    postgres_user: str | None = None
    postgres_password: str | None = None
    postgres_db: str | None = None
    postgres_host: str | None = None
    postgres_port: int | None = None

    # Scraper behaviour
    request_timeout: int = 10
    connect_timeout: int = 5
    read_timeout: int = 15
    max_retries: int = 3
    backoff_factor: float = 0.5
    retry_status_codes: list[int] = [429, 500, 502, 503, 504]
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Safety net only - any *future* unrelated env var (e.g. from your
        # shell, CI, or a new Docker var) won't crash the app. Real config
        # values should still be declared as fields above, not rely on this.
        extra="ignore",
    )


# Single settings instance to be imported across the app
settings = Settings()