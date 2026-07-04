"""Register Equipment Registry's own permission catalog entries in IAM
(iam-module.md §7.3: "a corresponding Permission catalog entry is
registered in IAM as part of that module's own deployment/seed process").

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

Mirrors app/modules/substation_registry/bootstrap.py's own pattern exactly.

Run standalone:
    python -m app.modules.equipment_registry.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

EQUIPMENT_REGISTRY_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "equipment_registry.read",
        "label": "Read circuits",
        "description": (
            "Read access to the Equipment Registry (Circuit/CircuitTerminal). "
            "Registered as catalog data for future finer-grained use; no "
            "endpoint currently gates on it, since read is treated as open "
            "to any authenticated user (equipment-registry-module.md §15)."
        ),
        "module_scope": "equipment_registry",
    },
    {
        "permission_id": "equipment_registry.write",
        "label": "Manage circuits",
        "description": (
            "Create/update circuits, add circuit terminals, and change a "
            "circuit's operational status (equipment-registry-module.md §9)."
        ),
        "module_scope": "equipment_registry",
    },
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": ["equipment_registry.read", "equipment_registry.write"],
    "Engineer": ["equipment_registry.write"],
    "Viewer": ["equipment_registry.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register Equipment Registry's permission catalog
    entries and grant them to IAM's baseline system roles."""
    repo = IAMRepository(db)
    service = IAMService(db)

    registered = {
        p["permission_id"]: service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in EQUIPMENT_REGISTRY_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping "
                "its Equipment Registry grants for now; re-run this script "
                "afterwards.",
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
        "Equipment Registry bootstrap complete: %d permission(s) registered.", len(registered)
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
