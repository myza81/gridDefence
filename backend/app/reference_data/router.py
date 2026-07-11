"""Read-only endpoints for Core Platform reference/lookup tables.

Not owned by any single business module — every module that references
voltage_level/region/state/grid_owner/operational_status (starting with
Substation Registry in Phase 2) needs the same read access to populate
lookups/dropdowns, so this lives alongside the shared reference data itself
rather than inside any one module's router (implementation-plan.md §1 places
`reference_data/` as a sibling of `modules/`, not a module itself).

Read-only: any authenticated user may list reference data (it is
non-sensitive lookup data, CLAUDE.md §11.3) — no permission gate beyond
authentication, mirroring the same pattern already used for IAM's own
`GET /roles` and `GET /permissions` catalog endpoints (app/modules/iam/router.py).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.iam.dependencies import get_current_user
from app.modules.iam.models import User
from app.reference_data.repository import ReferenceDataRepository
from app.reference_data.schemas import (
    GmZoneSummary,
    GridOwnerSummary,
    LineTypeSummary,
    OperationalStatusSummary,
    RegionSummary,
    StateSummary,
    TransformerBreakerNumberingConventionSummary,
    VoltageLevelSummary,
)

router = APIRouter(prefix="/reference-data", tags=["reference-data"])


@router.get("/voltage-levels", response_model=list[VoltageLevelSummary])
def list_voltage_levels(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[VoltageLevelSummary]:
    return ReferenceDataRepository(db).list_voltage_levels()


@router.get("/regions", response_model=list[RegionSummary])
def list_regions(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[RegionSummary]:
    return ReferenceDataRepository(db).list_regions()


@router.get("/gm-zones", response_model=list[GmZoneSummary])
def list_gm_zones(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[GmZoneSummary]:
    return ReferenceDataRepository(db).list_gm_zones()


@router.get("/states", response_model=list[StateSummary])
def list_states(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[StateSummary]:
    return ReferenceDataRepository(db).list_states()


@router.get("/grid-owners", response_model=list[GridOwnerSummary])
def list_grid_owners(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[GridOwnerSummary]:
    return ReferenceDataRepository(db).list_grid_owners()


@router.get("/operational-statuses", response_model=list[OperationalStatusSummary])
def list_operational_statuses(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[OperationalStatusSummary]:
    return ReferenceDataRepository(db).list_operational_statuses()


@router.get("/line-types", response_model=list[LineTypeSummary])
def list_line_types(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[LineTypeSummary]:
    return ReferenceDataRepository(db).list_line_types()


@router.get(
    "/transformer-breaker-numbering-conventions",
    response_model=list[TransformerBreakerNumberingConventionSummary],
)
def list_transformer_breaker_numbering_conventions(
    db: Session = Depends(get_db), _current_user: User = Depends(get_current_user)
) -> list[TransformerBreakerNumberingConventionSummary]:
    return ReferenceDataRepository(db).list_transformer_breaker_numbering_conventions()
