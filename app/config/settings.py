# app/config/settings.py
"""
Application configuration module.

Loads settings from environment variables / .env file using pydantic-settings.
Centralizing configuration here keeps the rest of the codebase free of
hard-coded values (timeouts, retries, DB URL, etc.).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings, populated from environment variables."""

    # General app info
    app_name: str = "Smart Web Scraper API"
    app_version: str = "1.0.0"
    debug: bool = True

    # Database
    database_url: str = "sqlite:///./scraper.db"

    # Scraper behaviour
    request_timeout: int = 10          # legacy/reference value, kept for compatibility
    connect_timeout: int = 5           # max seconds to establish a connection
    read_timeout: int = 15             # max seconds to wait for a response
    max_retries: int = 3               # total retry attempts on retryable failures
    backoff_factor: float = 0.5        # delay multiplier between retries
    retry_status_codes: list[int] = [429, 500, 502, 503, 504]
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


# Single settings instance to be imported across the app
settings = Settings()