"""Register the UFLS module's own permission catalog entries in IAM
(iam-module.md §7.3: "a corresponding Permission catalog entry is
registered in IAM as part of that module's own deployment/seed process").

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

**No UFLS Scheme/Version data is seeded here.** No authoritative document
defines an approved initial UFLS scheme (this sprint's own instructions
explicitly forbid inventing default engineering records). The module
starts empty; an authorized Engineer or Administrator creates the first
scheme/Draft through the ordinary API.

Permission model: `ufls.publish` and `ufls.enter_in_error` are
Administrator-only — mirroring stage_setting_registry's own precedent
(itself mirroring findings-and-publication-governance-architecture.md
§6's "Only Administrators may publish"), generalized to this module's
own analogous ADR-015 lifecycle actions. Engineer holds
`.read`/`.manage` (scheme/Draft creation, stage and assignment editing
while Draft) only.

Run standalone:
    python -m app.modules.ufls.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

UFLS_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "ufls.read",
        "label": "Read UFLS schemes",
        "description": (
            "Read access to UFLS scheme lineages, versions, stages, assignments, "
            "engineering summaries, and publication history."
        ),
        "module_scope": "ufls",
    },
    {
        "permission_id": "ufls.manage",
        "label": "Manage Draft UFLS versions",
        "description": (
            "Create UFLS scheme lineages and Draft versions, edit Draft metadata, "
            "and add/update/remove/move Draft stages and assignments — while Draft "
            "only (ADR-015)."
        ),
        "module_scope": "ufls",
    },
    {
        "permission_id": "ufls.publish",
        "label": "Publish UFLS versions",
        "description": (
            "Publish a Draft UFLS version, freezing its engineering content "
            "permanently and superseding the previous Published version of the "
            "same lineage. Administrator-only, distinct from ordinary Draft-"
            "editing access (ADR-015; mirrors stage_setting_registry's own "
            "Administrator-only Publish precedent)."
        ),
        "module_scope": "ufls",
    },
    {
        "permission_id": "ufls.enter_in_error",
        "label": "Mark UFLS versions Entered in Error",
        "description": (
            "Mark a UFLS version Entered in Error — an administrative correction, "
            "mandatory reason required (ADR-015)."
        ),
        "module_scope": "ufls",
    },
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": ["ufls.read", "ufls.manage", "ufls.publish", "ufls.enter_in_error"],
    "Engineer": ["ufls.read", "ufls.manage"],
    "Viewer": ["ufls.read"],
}


def run_bootstrap(db: Session) -> None:
    """Idempotently register this module's permission catalog entries and
    grant them to IAM's baseline system roles. Seeds no UFLS scheme
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
        for p in UFLS_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping its "
                "UFLS grants for now; re-run this script afterwards.",
                role_name,
            )
            continue
        for permission_id in permission_ids:
            if repo.get_role_permission(role.role_id, permission_id) is None:
                service.grant_permission_to_role(
                    role_id=role.role_id, permission_id=permission_id, actor_user_id=None
                )

    db.commit()
    logger.info("UFLS bootstrap complete: %d permission(s) registered.", len(registered))


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    db = SessionLocal()
    try:
        run_bootstrap(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
