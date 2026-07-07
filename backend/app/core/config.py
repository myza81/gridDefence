"""Application configuration.

Per CLAUDE.md §22: infrastructure configuration is externalised via environment
variables. Engineering parameters (thresholds, enforcement modes, etc.) belong
in the database once domain modules exist (CLAUDE.md A7) — this module never
holds engineering data, only deployment/runtime configuration.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# The repository root ".env" is the single source of truth for local
# configuration (used by both Docker Compose and local, non-Docker runs).
# This must be an absolute path: pydantic-settings resolves a relative
# `env_file` against the process's current working directory, not against
# this file's location — and DEVELOPMENT.md documents running the backend
# from `backend/` (`cd backend && uvicorn ...` / `cd backend && pytest`),
# not from the repo root. A relative ".env" would silently look for
# `backend/.env` (which does not exist) instead of the real root file.
# Docker Compose is unaffected either way — it injects real environment
# variables into the container directly, which always take priority over
# any `.env` file pydantic-settings would otherwise read.
_REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    """Environment-driven settings. See ../../.env.example for the full variable list."""

    model_config = SettingsConfigDict(
        env_file=_REPO_ROOT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Obviously-non-functional placeholder password — every real deployment
    # (local or otherwise) must override this via .env/the environment, same
    # convention as secret_key/bootstrap_admin_password below.
    database_url: str = (
        "postgresql+psycopg://engineering_app:changeme@localhost:5432/engineering_platform"
    )

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

    # PSS/E Integration (Phase 4) — Redis + RQ, introduced here per
    # implementation-plan.md §4 (first module with genuinely heavy async
    # computation: RAW file parsing/validation and EquipmentTopologyMap
    # matching, per psse-integration-module.md §18's own risk note).
    # `rq_async=False` is the test-environment escape hatch: the test suite
    # sets this so `app.core.queue.enqueue(...)` runs the job function
    # synchronously, in-process, against a `fakeredis` connection — no real
    # Redis server or background worker needed for correctness tests
    # (CLAUDE.md §18 tests business logic, not infrastructure plumbing).
    redis_url: str = "redis://localhost:6379/0"
    rq_async: bool = True

    # Execution Engine (Phase 6 architecture refinement — app.core.execution)
    # — configurable background execution. "direct" runs submitted work
    # in-process, in the calling thread: no Redis, no RQ, no worker process
    # required. This is the default, matching this project's own primary
    # deployment target (a small engineering team, typically fewer than 10
    # concurrent users, developing on company-managed Windows machines
    # where installing Redis may not always be possible). "queue" enqueues
    # via Redis+RQ exactly as before this refactor, for deployments that
    # want genuine background execution across a separate worker process.
    # See docs/architecture/psse-integration-module.md §8.9c.
    execution_mode: Literal["direct", "queue"] = "direct"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — avoids re-parsing the environment on every call."""
    return Settings()
