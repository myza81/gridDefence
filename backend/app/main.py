"""GridDefence backend entrypoint.

Wires the FastAPI application, the unversioned health check, and the
versioned /api/v1 router that every business module's own router attaches to
(docs/architecture/implementation-plan.md). Phase 1 added IAM's router;
Phase 2 adds Substation Registry's router and the shared, read-only Core
Platform reference-data router; Phase 3 adds Equipment Registry's
Circuit/CircuitTerminal router; Phase 4 adds PSS/E Integration's router;
Phase 5 adds the static Network Model's router; Phase 3.6 adds the
Automatic Load Shedding Functionality Registry's router; Phase 3.7 adds
the Sensitive Customer Registry's router.
"""

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.modules.automatic_load_shedding_functionality.router import (
    router as automatic_load_shedding_functionality_router,
)
from app.modules.equipment_registry.router import router as equipment_registry_router
from app.modules.equipment_registry.router import (
    transformer_router,
    transformer_terminal_router,
    voltage_yard_router,
)
from app.modules.iam.router import router as iam_router
from app.modules.network_model.router import router as network_model_router
from app.modules.psse_integration.router import router as psse_integration_router
from app.modules.sensitive_customer_registry.router import (
    router as sensitive_customer_registry_router,
)
from app.modules.substation_registry.router import router as substation_registry_router
from app.reference_data.router import router as reference_data_router

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
api_v1_router.include_router(reference_data_router)
api_v1_router.include_router(substation_registry_router)
api_v1_router.include_router(equipment_registry_router)
api_v1_router.include_router(voltage_yard_router)
api_v1_router.include_router(transformer_router)
api_v1_router.include_router(transformer_terminal_router)
api_v1_router.include_router(psse_integration_router)
api_v1_router.include_router(network_model_router)
api_v1_router.include_router(automatic_load_shedding_functionality_router)
api_v1_router.include_router(sensitive_customer_registry_router)
app.include_router(api_v1_router)


@app.get("/health", tags=["infrastructure"])
def health() -> dict[str, str]:
    """Unversioned liveness/readiness check — not a business endpoint."""
    return {"status": "ok", "environment": settings.environment}
