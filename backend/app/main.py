"""GridDefence backend entrypoint.

Wires the FastAPI application, the unversioned health check, and the
versioned /api/v1 router that every business module's own router attaches to
(docs/architecture/implementation-plan.md). Phase 1 adds IAM's router; no
other business module exists yet.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.iam.router import router as iam_router

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

# The versioned API router every business module's own router attaches to
# (CLAUDE.md §13, API-first, versioned contract).
api_v1_router = APIRouter(prefix=settings.api_v1_prefix)
api_v1_router.include_router(iam_router)
app.include_router(api_v1_router)


@app.get("/health", tags=["infrastructure"])
def health() -> dict[str, str]:
    """Unversioned liveness/readiness check — not a business endpoint."""
    return {"status": "ok", "environment": settings.environment}
