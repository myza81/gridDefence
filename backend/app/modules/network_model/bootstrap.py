"""Register Network Model's own permission catalog entry in IAM
(iam-module.md §7.3: "a corresponding Permission catalog entry is
registered in IAM as part of that module's own deployment/seed process").

Idempotent: safe to run on every startup/deploy. Mirrors
app/modules/equipment_registry/bootstrap.py's own pattern exactly.

Run standalone:
    python -m app.modules.network_model.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

NETWORK_MODEL_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "network_model.read",
        "label": "Read network model",
        "description": (
            "Read access to the static Network Model (connectivity, equipment "
            "relationships, traversal). Registered as catalog data for future "
            "finer-grained use; no endpoint currently gates on it, since read "
            "is treated as open to any authenticated user, mirroring "
            "Equipment Registry's and Substation Registry's own precedent."
        ),
        "module_scope": "network_model",
    },
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": ["network_model.read"],
    "Engineer": ["network_model.read"],
    "Viewer": ["network_model.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register Network Model's permission catalog entry and
    grant it to IAM's baseline system roles."""
    repo = IAMRepository(db)
    service = IAMService(db)

    registered = {
        p["permission_id"]: service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in NETWORK_MODEL_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping "
                "its Network Model grants for now; re-run this script afterwards.",
                role_name,
            )
            continue
        for permission_id in permission_ids:
            if repo.get_role_permission(role.role_id, permission_id) is None:
                service.grant_permission_to_role(
                    role_id=role.role_id, permission_id=permission_id, actor_user_id=None
                )

    db.commit()
    logger.info("Network Model bootstrap complete: %d permission(s) registered.", len(registered))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        run_bootstrap(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
