"""Synthetic scheme-version test fixture (this sprint's own instructions
§11) — a durable, reusable adapter demonstrating that
`PublicationRecordService.evaluate_and_record_publication` is entirely
scheme-module-agnostic.

No real scheme module exists yet (UFLS/UVLS/EMLS are all out of this
sprint's scope). This module constructs *only* the same plain value
contracts (`Finding`, `PublicationPrerequisiteResult`,
`AcknowledgementInput`, `PublicationRequest`) a real future scheme
module's own Publish action will supply — never an ORM model, never a
production `synthetic_scheme_version` table, never a route reachable
through the normal application router (this sprint's own instructions
§11: "avoid creating production `synthetic_scheme_version` tables";
"do not expose synthetic identifiers through the normal application
router"). Every function here is a plain, reusable factory — import
these directly from any later shared-platform test file, in this module
or a future one; the two pytest fixtures at the bottom are a thin,
optional convenience layer for tests already using this module's own
`conftest.py`.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)
from app.modules.findings_publication_governance.publication import (
    AcknowledgementInput,
    PublicationPrerequisiteResult,
    PublicationRequest,
)


def synthetic_finding(**overrides: Any) -> Finding:
    """One synthetic `Finding` — the exact shape a real future detector
    would produce, with sensible defaults every test can override."""
    defaults: dict[str, Any] = {
        "finding_type": FindingType.MW_TOLERANCE_DEVIATION,
        "severity": Severity.WARNING,
        "source": "synthetic_scheme.mw_tolerance_detector",
        "description": "Synthetic finding for shared-platform publication testing.",
        "affected_object_type": "stage",
        "affected_object_id": "synthetic-stage-1",
    }
    defaults.update(overrides)
    return Finding(**defaults)


def synthetic_prerequisite(**overrides: Any) -> PublicationPrerequisiteResult:
    """One synthetic, passing structural prerequisite — the exact shape
    a real future scheme module's own ADR-015 prerequisite checks would
    supply."""
    defaults: dict[str, Any] = {
        "prerequisite_code": "SYNTHETIC_SCHEME_IDENTITY_PRESENT",
        "passed": True,
        "description": "Synthetic scheme identity is present.",
        "source": "synthetic_scheme_adapter",
    }
    defaults.update(overrides)
    return PublicationPrerequisiteResult(**defaults)


def synthetic_acknowledgement(
    finding_index: int, *, acknowledged_by_user_id: uuid.UUID, **overrides: Any
) -> AcknowledgementInput:
    defaults: dict[str, Any] = {
        "finding_index": finding_index,
        "acknowledged_by_user_id": acknowledged_by_user_id,
        "justification": "Reviewed and accepted for synthetic-scheme testing.",
    }
    defaults.update(overrides)
    return AcknowledgementInput(**defaults)


def synthetic_publication_request(
    *, published_by_user_id: uuid.UUID, **overrides: Any
) -> PublicationRequest:
    """A ready-to-use, minimally-valid `PublicationRequest` — one passing
    prerequisite, no findings, a fresh idempotency key. Every field can be
    overridden so a test can exercise any scenario (blocked findings,
    acknowledgement requirements, duplicate events, etc.) without
    constructing the whole contract by hand each time."""
    defaults: dict[str, Any] = {
        "publication_event_id": uuid.uuid4(),
        "scheme_type": SchemeType.UFLS,
        "scheme_version_id": uuid.uuid4(),
        "published_by_user_id": published_by_user_id,
        "findings": [],
        "prerequisites": [synthetic_prerequisite()],
        "acknowledgements": [],
    }
    defaults.update(overrides)
    return PublicationRequest(**defaults)


@pytest.fixture()
def synthetic_scheme_request_factory(actor_user_id: uuid.UUID):
    """Pytest-fixture convenience wrapper over `synthetic_publication_request`
    — returns a callable so each test builds its own request, with its own
    overrides, while reusing the same synthetic-scheme defaults and the
    module's own `actor_user_id` fixture as the default publisher."""

    def _factory(**overrides: Any) -> PublicationRequest:
        overrides.setdefault("published_by_user_id", actor_user_id)
        return synthetic_publication_request(**overrides)

    return _factory
