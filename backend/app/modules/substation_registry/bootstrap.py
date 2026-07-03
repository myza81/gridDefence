"""Register Substation Registry's own permission catalog entries in IAM
(iam-module.md §7.3: "a corresponding Permission catalog entry is
registered in IAM as part of that module's own deployment/seed process —
never written at runtime by the other module's own service layer").

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

`substation_registry.write` is granted to `Administrator` (which "bundles
the full set" of elevated permissions, iam-module.md §7.9) and to
`Engineer` ("Modules grant their own Editor-tier permissions to this role
as they are built" — app/modules/iam/bootstrap.py's own baseline-role
description, written in anticipation of exactly this). `substation_registry
.read` is granted to `Administrator` and `Viewer` for completeness, even
though no endpoint in this module currently gates on it (substation-registry
.md §10 — read is open to any authenticated user); see Phase 2's final
report ("Assumptions made").

Run standalone:
    python -m app.modules.substation_registry.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

SUBSTATION_REGISTRY_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "substation_registry.read",
        "label": "Read substations",
        "description": (
            "Read access to the Substation Registry. Registered as catalog "
            "data for future finer-grained use; no endpoint currently gates "
            "on it, since substation-registry.md §10 treats read as open to "
            "any authenticated user."
        ),
        "module_scope": "substation_registry",
    },
    {
        "permission_id": "substation_registry.write",
        "label": "Manage substations",
        "description": (
            "Create/update substations and change their operational status "
            "(substation-registry.md §10)."
        ),
        "module_scope": "substation_registry",
    },
]

# Baseline role -> permission_id grants, per iam-module.md §7.9's pattern of
# each module extending IAM's existing baseline roles as it is built.
_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": ["substation_registry.read", "substation_registry.write"],
    "Engineer": ["substation_registry.write"],
    "Viewer": ["substation_registry.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register Substation Registry's permission catalog
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
        for p in SUBSTATION_REGISTRY_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping "
                "its Substation Registry grants for now; re-run this script "
                "afterwards.",
                role_name,
            )
            continue
        for permission_id in permission_ids:
            if repo.get_role_permission(role.role_id, permission_id) is None:
                service.grant_permission_to_role(
                    role_id=role.role_id,
                    permission_id=permission_id,
                    actor_user_id=role.created_by_user_id,
                )

    db.commit()
    logger.info(
        "Substation Registry bootstrap complete: %d permission(s) registered.", len(registered)
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
