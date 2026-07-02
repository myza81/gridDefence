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

    # --- IAM (docs/architecture/iam-module.md §4 — authentication mechanics
    # are an implementation detail outside architectural scope; the specific
    # token scheme and its secret/TTL are configured here as ordinary
    # infrastructure config, CLAUDE.md §22). Never a real secret by default —
    # every deployment must override this via the environment.
    secret_key: str = "insecure-development-secret-change-me"
    access_token_ttl_seconds: int = 8 * 60 * 60  # 8 hours

    # Bootstrap Administrator (app/modules/iam/bootstrap.py) — read only when
    # no Administrator-role user exists yet.
    bootstrap_admin_username: str = "admin"
    bootstrap_admin_password: str = "change-me-immediately"
    bootstrap_admin_email: str | None = None

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-parsing the environment on every call."""
    return Settings()
