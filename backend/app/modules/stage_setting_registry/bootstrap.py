"""Register the Stage Setting Registry's own permission catalog entries in
IAM (iam-module.md §7.3: "a corresponding Permission catalog entry is
registered in IAM as part of that module's own deployment/seed process").

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

**No Stage Setting Sets are seeded here.** stage-setting-set-architecture.md
defines no approved initial engineering records — this sprint's own
instructions explicitly forbid inventing default UFLS/UVLS thresholds. The
module starts empty; an authorized Engineer or Administrator creates the
first Draft through the ordinary API.

Permission model: `stage_setting_registry.publish` and
`stage_setting_registry.enter_in_error` are Administrator-only — mirroring
findings-and-publication-governance-architecture.md §6's own "Only
Administrators may publish" precedent, generalized to this module's
analogous lifecycle actions (a user who may edit a Draft is not assumed to
also be trusted to publish or correct it — this sprint's own instructions,
§10). Engineer holds `.read`/`.manage` only.

Run standalone:
    python -m app.modules.stage_setting_registry.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

STAGE_SETTING_REGISTRY_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "stage_setting_registry.read",
        "label": "Read Stage Setting Sets",
        "description": (
            "Read access to the Stage Setting Registry. Registered as catalog data for "
            "possible future finer-grained use; no endpoint currently gates on it, since read "
            "is treated as open to any authenticated user "
            "(stage-setting-set-architecture.md; mirrors every other registry's own precedent)."
        ),
        "module_scope": "stage_setting_registry",
    },
    {
        "permission_id": "stage_setting_registry.manage",
        "label": "Manage Draft Stage Setting Sets",
        "description": (
            "Create Draft Stage Setting Sets, edit their metadata, and add/update/remove/"
            "reorder their Stage Settings — while Draft only "
            "(stage-setting-set-architecture.md §6, §8)."
        ),
        "module_scope": "stage_setting_registry",
    },
    {
        "permission_id": "stage_setting_registry.publish",
        "label": "Publish Stage Setting Sets",
        "description": (
            "Publish a Draft Stage Setting Set, freezing its structure permanently. "
            "Administrator-only, distinct from ordinary Draft-editing access "
            "(stage-setting-set-architecture.md §6; mirrors "
            "findings-and-publication-governance-architecture.md §6's own "
            "Administrator-only Publish precedent)."
        ),
        "module_scope": "stage_setting_registry",
    },
    {
        "permission_id": "stage_setting_registry.enter_in_error",
        "label": "Mark Stage Setting Sets Entered in Error",
        "description": (
            "Mark a Published Stage Setting Set Entered in Error — an administrative "
            "correction, mandatory reason required (stage-setting-set-architecture.md §6)."
        ),
        "module_scope": "stage_setting_registry",
    },
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": [
        "stage_setting_registry.read",
        "stage_setting_registry.manage",
        "stage_setting_registry.publish",
        "stage_setting_registry.enter_in_error",
    ],
    "Engineer": ["stage_setting_registry.read", "stage_setting_registry.manage"],
    "Viewer": ["stage_setting_registry.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register this module's permission catalog entries and
    grant them to IAM's baseline system roles. Seeds no Stage Setting Set
    data — see module docstring."""
    repo = IAMRepository(db)
    service = IAMService(db)

    registered = {
        p["permission_id"]: service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in STAGE_SETTING_REGISTRY_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping its "
                "Stage Setting Registry grants for now; re-run this script afterwards.",
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
        "Stage Setting Registry bootstrap complete: %d permission(s) registered.",
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
