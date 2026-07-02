"""GridDefence backend entrypoint.

Phase 0 (Repository Foundation): wires the FastAPI application, the
unversioned health check, and the empty /api/v1 router that future business
modules attach their own routers to (docs/architecture/implementation-plan.md
Phase 0). No business logic or domain routes exist yet.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging()

app = FastAPI(
    title="GridDefence",
    description="Engineering platform for transmission grid defence schemes.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# The versioned API router every future module's own router attaches to
# (e.g. `api_v1_router.include_router(iam_router)` once Phase 1 exists).
# Intentionally empty in Phase 0 — CLAUDE.md §13, API-first, versioned contract.
api_v1_router = APIRouter(prefix=settings.api_v1_prefix)
app.include_router(api_v1_router)


@app.get("/health", tags=["infrastructure"])
def health() -> dict[str, str]:
    """Unversioned liveness/readiness check — not a business endpoint."""
    return {"status": "ok", "environment": settings.environment}
