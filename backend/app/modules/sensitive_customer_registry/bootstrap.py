"""Register the Sensitive Customer Registry's own permission catalog
entries in IAM (iam-module.md §7.3: "a corresponding Permission catalog
entry is registered in IAM as part of that module's own deployment/seed
process").

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

Permission model (implementation spec §12, corrected — Administrator-only
mutation): this registry is global authoritative engineering knowledge
that scheme engineers consume but do not own. Engineer holds `.read` only
— no `.write` grant, unlike ALSF's own precedent. No new role is
introduced.

Mirrors app/modules/automatic_load_shedding_functionality/bootstrap.py's
own pattern, with the corrected role-grant table.

Run standalone:
    python -m app.modules.sensitive_customer_registry.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

SENSITIVE_CUSTOMER_REGISTRY_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "sensitive_customer_registry.read",
        "label": "Read sensitive customer registry records",
        "description": (
            "Read access to active Sensitive Customer Registry data required for engineering "
            "work — list/detail/audit-history/lookup/batch-lookup/summary "
            "(sensitive-customer-registry-module.md §15)."
        ),
        "module_scope": "sensitive_customer_registry",
    },
    {
        "permission_id": "sensitive_customer_registry.write",
        "label": "Manage sensitive customer registry records",
        "description": (
            "Create/edit Sensitive Facility records, reassign Transformer Terminal "
            "associations, and change lifecycle status (archive/reactivate/entered-in-error). "
            "Administrator-only — this registry is global authoritative engineering knowledge "
            "that scheme engineers consume but do not own "
            "(sensitive-customer-registry-implementation-spec.md §12)."
        ),
        "module_scope": "sensitive_customer_registry",
    },
    {
        "permission_id": "sensitive_customer_registry.manage_reference_data",
        "label": "Manage sensitive customer registry reference data",
        "description": (
            "Create/edit/activate/deactivate Facility Sector and Sensitivity Classification "
            "reference data. Administrator-only "
            "(sensitive-customer-registry-implementation-spec.md §8, §12)."
        ),
        "module_scope": "sensitive_customer_registry",
    },
]

# Corrected permission model (task Correction 1): Engineer holds `.read`
# only — no `.write` or `.manage_reference_data` grant. No new role is
# introduced; only the three existing baseline roles are used.
_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": [
        "sensitive_customer_registry.read",
        "sensitive_customer_registry.write",
        "sensitive_customer_registry.manage_reference_data",
    ],
    "Engineer": ["sensitive_customer_registry.read"],
    "Viewer": ["sensitive_customer_registry.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register this module's permission catalog entries and
    grant them to IAM's baseline system roles."""
    repo = IAMRepository(db)
    service = IAMService(db)

    registered = {
        p["permission_id"]: service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in SENSITIVE_CUSTOMER_REGISTRY_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping its "
                "Sensitive Customer Registry grants for now; re-run this script afterwards.",
                role_name,
            )
            continue
        for permission_id in permission_ids:
            if repo.get_role_permission(role.role_id, permission_id) is None:
                service.grant_permission_to_role(
                    role_id=role.role_id, permission_id=permission_id, actor_user_id=None
                )

    db.commit()
    logger.info(
        "Sensitive Customer Registry bootstrap complete: %d permission(s) registered.",
        len(registered),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        run_bootstrap(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
