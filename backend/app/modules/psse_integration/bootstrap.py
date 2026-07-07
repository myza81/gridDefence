"""Register PSS/E Integration's own permission catalog entries in IAM
(iam-module.md §7.3: "a corresponding Permission catalog entry is
registered in IAM as part of that module's own deployment/seed process").

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

Mirrors app/modules/equipment_registry/bootstrap.py's own pattern exactly.

Activation is deliberately withheld from the Engineer role: activation is
"explicit, privileged, atomic, and audited" (Phase 4 requirements) — an
Engineer may upload and commit imports for review, but only an
Administrator may promote a committed batch to Current.

Run standalone:
    python -m app.modules.psse_integration.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

PSSE_INTEGRATION_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "psse_integration.read",
        "label": "Read PSS/E imports",
        "description": (
            "Read access to import batches, topology versions, load "
            "snapshots, and EquipmentTopologyMap review data."
        ),
        "module_scope": "psse_integration",
    },
    {
        "permission_id": "psse_integration.import",
        "label": "Import PSS/E RAW files",
        "description": (
            "Upload, preview, and commit PSS/E RAW files. Commit persists "
            "imported data but never makes it Current."
        ),
        "module_scope": "psse_integration",
    },
    {
        "permission_id": "psse_integration.activate",
        "label": "Activate PSS/E imports",
        "description": (
            "Promote a committed import batch's TopologyVersion/LoadSnapshot "
            "to Current, superseding the previous Current record. Explicit, "
            "privileged, atomic, and audited."
        ),
        "module_scope": "psse_integration",
    },
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": [
        "psse_integration.read",
        "psse_integration.import",
        "psse_integration.activate",
    ],
    "Engineer": ["psse_integration.read", "psse_integration.import"],
    "Viewer": ["psse_integration.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register PSS/E Integration's permission catalog entries
    and grant them to IAM's baseline system roles."""
    repo = IAMRepository(db)
    service = IAMService(db)

    registered = {
        p["permission_id"]: service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in PSSE_INTEGRATION_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping "
                "its PSS/E Integration grants for now; re-run this script "
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
        "PSS/E Integration bootstrap complete: %d permission(s) registered.", len(registered)
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
