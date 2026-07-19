"""Register Engineering Parameter Configuration's own permission catalog
entries in IAM (iam-module.md §7.3: "a corresponding Permission catalog
entry is registered in IAM as part of that module's own deployment/seed
process"), and idempotently seed the one architecture-approved engineering
parameter — `mw_tolerance_percentage` (continuous-evaluation-architecture.md
§7; ADR-021) — no other parameter is invented here.

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

Permission model (ADR-021 §4.1, mirroring
app/modules/sensitive_customer_registry/bootstrap.py's own "Administrator-
only mutation" precedent): `engineering_parameters.manage` is Administrator-
only — changing a platform-wide policy value is a platform administration
action, distinct from ordinary Editor-tier scheme-design permissions.
Engineer and Viewer both hold `.read` only.

The initial parameter value is seeded through this module's own
`EngineeringParameterService.set_parameter_value` — the same single,
audited write path any future Administrator-driven change uses —
with `actor_user_id=None`, mirroring every other module's own bootstrap
convention for `grant_permission_to_role`.

Run standalone:
    python -m app.modules.engineering_parameters.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

ENGINEERING_PARAMETERS_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "engineering_parameters.read",
        "label": "Read engineering parameter values",
        "description": (
            "Read access to current engineering parameter values (e.g. the MW "
            "tolerance) — any authenticated user (engineering-parameter-"
            "configuration-architecture.md §15)."
        ),
        "module_scope": "engineering_parameters",
    },
    {
        "permission_id": "engineering_parameters.manage",
        "label": "Manage engineering parameter values",
        "description": (
            "Set an engineering parameter's current value and read its audit "
            "history. Administrator-only — changing a platform-wide policy "
            "value is a platform administration action "
            "(engineering-parameter-configuration-architecture.md §15; ADR-021 §4.1)."
        ),
        "module_scope": "engineering_parameters",
    },
]

# Administrator-only mutation (ADR-021 §4.1) — Engineer and Viewer hold
# `.read` only, mirroring sensitive_customer_registry's own precedent for
# platform-wide, engineer-consumed-but-not-owned data.
_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": ["engineering_parameters.read", "engineering_parameters.manage"],
    "Engineer": ["engineering_parameters.read"],
    "Viewer": ["engineering_parameters.read"],
}

# The one architecture-approved initial parameter (ADR-021; continuous-
# evaluation-architecture.md §7) — do not add further parameters here
# without a corresponding architecture decision.
_INITIAL_PARAMETERS: list[dict[str, str]] = [
    {
        "parameter_key": "mw_tolerance_percentage",
        "value": "10",
        "unit": "percent",
        "description": (
            "Global engineering tolerance for MW allocation deviation "
            "(continuous-evaluation-architecture.md §7): a stage/priority "
            "group's current MW may deviate from target MW by up to this "
            "percentage, in either direction, before an out-of-tolerance "
            "finding is raised."
        ),
    },
]


def run_bootstrap(db: Session) -> None:
    """Idempotently register this module's permission catalog entries,
    grant them to IAM's baseline system roles, and seed the one
    architecture-approved initial parameter value if it does not already
    exist."""
    repo = IAMRepository(db)
    iam_service = IAMService(db)

    registered = {
        p["permission_id"]: iam_service.register_permission(
            permission_id=p["permission_id"],
            label=p["label"],
            description=p["description"],
            module_scope=p["module_scope"],
        )
        for p in ENGINEERING_PARAMETERS_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping its "
                "Engineering Parameter Configuration grants for now; re-run this "
                "script afterwards.",
                role_name,
            )
            continue
        for permission_id in permission_ids:
            if repo.get_role_permission(role.role_id, permission_id) is None:
                iam_service.grant_permission_to_role(
                    role_id=role.role_id, permission_id=permission_id, actor_user_id=None
                )

    parameter_service = EngineeringParameterService(db)
    for parameter in _INITIAL_PARAMETERS:
        if parameter_service.get_parameter(parameter["parameter_key"]) is not None:
            continue
        parameter_service.set_parameter_value(
            parameter["parameter_key"],
            value=parameter["value"],
            unit=parameter["unit"],
            description=parameter["description"],
            change_reason="Initial value seeded at deployment (ADR-021).",
            actor_user_id=None,
        )

    db.commit()
    logger.info(
        "Engineering Parameter Configuration bootstrap complete: %d permission(s) "
        "registered, %d initial parameter(s) ensured.",
        len(registered),
        len(_INITIAL_PARAMETERS),
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
