"""Register Findings and Publication Governance's own permission catalog
entries in IAM (iam-module.md §7.3), and idempotently seed the four
architecture-approved severity-keyed baseline policies —
findings-and-publication-governance-architecture.md §4.2 — no other
policy (per-finding-type, per-scheme, or otherwise) is invented here.

Idempotent: safe to run on every startup/deploy, including against a
database where IAM's own bootstrap (app/modules/iam/bootstrap.py) has
already run and created the baseline Administrator/Engineer/Viewer roles.

Permission model: `findings_publication_governance.manage_policy` and
`.view_audit` are both Administrator-only — mirroring module document
§4.1's own elevated-tier precedent ("distinct from the Editor/Approver-
tier permissions that govern ordinary scheme design") and
`engineering_parameters/bootstrap.py`'s own "Administrator-only mutation"
precedent for platform-wide governance data. Engineer and Viewer both
hold `.read` only — ordinary scheme editors never change publication
governance (this sprint's own instructions §10).

The four baseline policies are seeded through this module's own
`PublicationTreatmentPolicyService.create_policy` — the same single,
audited write path any future Administrator-driven override uses — with
`actor_user_id=None`, mirroring `engineering_parameters/bootstrap.py`'s
own documented convention exactly.

Run standalone:
    python -m app.modules.findings_publication_governance.bootstrap
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.modules.findings_publication_governance.service import PublicationTreatmentPolicyService
from app.modules.iam.repository import IAMRepository
from app.modules.iam.service import IAMService

logger = logging.getLogger(__name__)

FINDINGS_PUBLICATION_GOVERNANCE_PERMISSIONS: list[dict[str, str]] = [
    {
        "permission_id": "findings_publication_governance.read",
        "label": "Read Publication Treatment Policies",
        "description": (
            "Read access to configured Publication Treatment Policies — any authenticated "
            "user (findings-and-publication-governance-architecture.md §10: "
            "'publication-treatment-policies — read (broad)')."
        ),
        "module_scope": "findings_publication_governance",
    },
    {
        "permission_id": "findings_publication_governance.manage_policy",
        "label": "Manage Publication Treatment Policies",
        "description": (
            "Create, update, and remove Publication Treatment Policies. Administrator-only — "
            "an elevated, admin-tier permission distinct from ordinary Editor/Approver-tier "
            "scheme-design permissions (findings-and-publication-governance-architecture.md "
            "§4.1)."
        ),
        "module_scope": "findings_publication_governance",
    },
    {
        "permission_id": "findings_publication_governance.view_audit",
        "label": "View Publication Treatment Policy audit history",
        "description": (
            "Read a Publication Treatment Policy's own change history. Administrator-only — "
            "audit log access is itself access-controlled "
            "(findings-and-publication-governance-architecture.md §13; CLAUDE.md A10)."
        ),
        "module_scope": "findings_publication_governance",
    },
]

_ROLE_GRANTS: dict[str, list[str]] = {
    "Administrator": [
        "findings_publication_governance.read",
        "findings_publication_governance.manage_policy",
        "findings_publication_governance.view_audit",
    ],
    "Engineer": ["findings_publication_governance.read"],
    "Viewer": ["findings_publication_governance.read"],
}

# The four architecture-approved initial baseline policies (module
# document §4.2) — keyed by severity alone (finding_type=None,
# scheme_type=None). Do not add further rows here without a corresponding
# architecture decision.
_INITIAL_BASELINE_POLICIES: list[dict[str, str]] = [
    {
        "severity": "CRITICAL",
        "treatment": "BLOCK",
        "reason": (
            "Initial baseline seeded at deployment (findings-and-publication-governance-"
            "architecture.md §4.2) — carried forward from the Prohibited critical-asset "
            "default (critical-infrastructure-module.md §7.4; emls-module.md §7.7)."
        ),
    },
    {
        "severity": "WARNING",
        "treatment": "ALLOW_WITH_ACKNOWLEDGEMENT",
        "reason": (
            "Initial baseline seeded at deployment (findings-and-publication-governance-"
            "architecture.md §4.2) — a Warning-severity finding must be consciously seen and "
            "accepted before Publication, but does not by itself block it."
        ),
    },
    {
        "severity": "ADVISORY",
        "treatment": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "reason": (
            "Initial baseline seeded at deployment (findings-and-publication-governance-"
            "architecture.md §4.2) — informative context, not serious enough to require "
            "explicit acknowledgement."
        ),
    },
    {
        "severity": "INFORMATION",
        "treatment": "ALLOW_WITHOUT_ACKNOWLEDGEMENT",
        "reason": (
            "Initial baseline seeded at deployment (findings-and-publication-governance-"
            "architecture.md §4.2) — same reasoning as Advisory, at a lower severity still."
        ),
    },
]


def run_bootstrap(db: Session) -> None:
    """Idempotently register this module's permission catalog entries,
    grant them to IAM's baseline system roles, and seed the four
    architecture-approved baseline policies if they do not already
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
        for p in FINDINGS_PUBLICATION_GOVERNANCE_PERMISSIONS
    }

    for role_name, permission_ids in _ROLE_GRANTS.items():
        role = repo.get_role_by_name(role_name)
        if role is None:
            logger.warning(
                "Bootstrap: baseline role '%s' does not exist yet — run IAM's own "
                "bootstrap (python -m app.modules.iam.bootstrap) first. Skipping its "
                "Findings and Publication Governance grants for now; re-run this "
                "script afterwards.",
                role_name,
            )
            continue
        for permission_id in permission_ids:
            if repo.get_role_permission(role.role_id, permission_id) is None:
                iam_service.grant_permission_to_role(
                    role_id=role.role_id, permission_id=permission_id, actor_user_id=None
                )

    policy_service = PublicationTreatmentPolicyService(db)
    seeded = 0
    for baseline in _INITIAL_BASELINE_POLICIES:
        if policy_service.repo.find_policy(
            severity=baseline["severity"], finding_type=None, scheme_type=None
        ):
            continue
        policy_service.create_policy(
            severity=baseline["severity"],
            finding_type=None,
            scheme_type=None,
            treatment=baseline["treatment"],
            change_reason=baseline["reason"],
            actor_user_id=None,
        )
        seeded += 1

    db.commit()
    logger.info(
        "Findings and Publication Governance bootstrap complete: %d permission(s) "
        "registered, %d baseline polic(y/ies) seeded.",
        len(registered),
        seeded,
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
