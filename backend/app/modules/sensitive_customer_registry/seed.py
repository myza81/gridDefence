"""Idempotent seed data for the Sensitive Customer Registry's own
module-owned reference tables (`facility_sector`, `sensitivity_classification`)
— deliberately not Core Platform's `app/reference_data/` package, since
these are this module's own domain vocabulary (ADR-012 decision 3;
implementation spec §4, §13).

Follows the exact convention already established by
`app/reference_data/seed.py`: idempotent, insert-if-missing (keyed on the
stable `code` column), a separate manual step from `alembic upgrade head`
— never run automatically on startup or by the migration itself
(implementation spec §13, Correction 6). A re-run never reverts an
administrator's subsequent edits to `label`/`sort_order`/`is_active` — this
script only ever inserts rows whose `code` is not yet present.

Seed values — the eight approved Facility Sectors and three approved
Sensitivity Classifications (Agreed Engineering Principles 3-4; module
document §7.2; implementation spec §13).

Run standalone:
    python -m app.modules.sensitive_customer_registry.seed
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

# `FacilitySector`/`SensitivityClassification` reference IAM's `user` table
# by FK (table-name string only, per CLAUDE.md A1 — no Python import of IAM
# needed for that reference itself). But SQLAlchemy still needs the `user`
# Table object present in `Base.metadata` to resolve that FK when sorting
# tables at flush time. When this module is run standalone
# (`python -m app.modules.sensitive_customer_registry.seed`), nothing else
# triggers that registration — unlike `bootstrap.py`, which incidentally
# imports `app.modules.iam.repository`/`.service` (and therefore
# `iam.models`) already. Mirrors the explicit import already required by
# `alembic/env.py` and `backend/conftest.py` for the identical reason.
from app.modules.iam import models as iam_models  # noqa: F401
from app.modules.sensitive_customer_registry.models import (
    FacilitySector,
    SensitivityClassification,
)

logger = logging.getLogger(__name__)

# Seed-created rows have no real IAM actor — seeding is an unattended
# deployment step, not a human action. `created_by_user_id`/
# `updated_by_user_id` are nullable on both reference tables specifically
# to accommodate this (models.py); every edit made through the service
# layer always supplies a real, authenticated actor instead.

FACILITY_SECTORS: list[dict[str, object]] = [
    {"code": "HEALTHCARE", "label": "Healthcare", "sort_order": 1},
    {
        "code": "SECURITY_DEFENCE_EMERGENCY",
        "label": "Security, Defence & Emergency Services",
        "sort_order": 2,
    },
    {
        "code": "GOVERNMENT_PUBLIC_ADMIN",
        "label": "Government & Public Administration",
        "sort_order": 3,
    },
    {"code": "TRANSPORT", "label": "Transport", "sort_order": 4},
    {"code": "UTILITIES", "label": "Utilities", "sort_order": 5},
    {
        "code": "STRATEGIC_ECONOMIC_INFRASTRUCTURE",
        "label": "Strategic & Economic Infrastructure",
        "sort_order": 6,
    },
    {
        "code": "SPECIAL_PROTECTED_CUSTOMERS",
        "label": "Special or Protected Customers",
        "sort_order": 7,
    },
    {"code": "OTHER_SENSITIVE_CONSUMER", "label": "Other Sensitive Consumer", "sort_order": 8},
]

# sort_order is semantically meaningful here — lower means higher
# sensitivity (module document §7.2; implementation spec §5.3).
SENSITIVITY_CLASSIFICATIONS: list[dict[str, object]] = [
    {"code": "HIGH", "label": "High", "sort_order": 1},
    {"code": "MEDIUM", "label": "Medium", "sort_order": 2},
    {"code": "LOW", "label": "Low", "sort_order": 3},
]


def _seed_facility_sectors(db: Session) -> int:
    existing = {s.code for s in db.query(FacilitySector).all()}
    created = 0
    for row in FACILITY_SECTORS:
        if row["code"] in existing:
            continue
        db.add(
            FacilitySector(
                code=row["code"],
                label=row["label"],
                sort_order=row["sort_order"],
                description=None,
                is_active=True,
                created_by_user_id=None,
                updated_by_user_id=None,
            )
        )
        created += 1
    return created


def _seed_sensitivity_classifications(db: Session) -> int:
    existing = {c.code for c in db.query(SensitivityClassification).all()}
    created = 0
    for row in SENSITIVITY_CLASSIFICATIONS:
        if row["code"] in existing:
            continue
        db.add(
            SensitivityClassification(
                code=row["code"],
                label=row["label"],
                sort_order=row["sort_order"],
                description=None,
                is_active=True,
                created_by_user_id=None,
                updated_by_user_id=None,
            )
        )
        created += 1
    return created


def run_seed(db: Session) -> dict[str, int]:
    """Idempotently seed both module-owned reference tables. Safe to call
    on every startup/deploy — rows already present (matched by their
    stable `code`) are left untouched, never duplicated or overwritten."""
    counts = {
        "facility_sector": _seed_facility_sectors(db),
        "sensitivity_classification": _seed_sensitivity_classifications(db),
    }
    db.commit()
    logger.info("Sensitive Customer Registry reference data seed complete: %s", counts)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
