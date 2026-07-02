"""Application configuration.

Per CLAUDE.md §22: infrastructure configuration is externalised via environment
variables. Engineering parameters (thresholds, enforcement modes, etc.) belong
in the database once domain modules exist (CLAUDE.md A7) — this module never
holds engineering data, only deployment/runtime configuration.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. See ../../.env.example for the full variable list."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = "postgresql+psycopg://griddefence:griddefence@localhost:5432/griddefence"

    api_v1_prefix: str = "/api/v1"

    cors_allowed_origins: list[str] = ["http://localhost:5173"]

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-parsing the environment on every call."""
    return Settings()
