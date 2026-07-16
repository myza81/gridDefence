"""Synthetic evaluation-input fixtures (this sprint's own instructions
§15: "provide reusable synthetic factories for tests — no production
synthetic records or APIs").

No real scheme module exists yet, so every function here constructs only
plain value contracts (`MwAssignmentGroupInput`, `EvaluationRequest`) —
never an ORM model, never a route reachable through the normal
application router. Mirrors `findings_publication_governance.tests.
synthetic_scheme`'s own established shape for this module's own contracts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.modules.continuous_evaluation.provider import EvaluationRequestProvider
from app.modules.continuous_evaluation.resolver import AffectedSchemeResolver
from app.modules.continuous_evaluation.schemas import (
    ChangeDescriptor,
    EvaluationRequest,
    EvaluationTarget,
    MwAssignmentGroupInput,
    MwEvaluationInputs,
)
from app.modules.findings_publication_governance.findings import SchemeType


def synthetic_mw_group(**overrides: Any) -> MwAssignmentGroupInput:
    defaults: dict[str, Any] = {
        "group_id": "stage-1",
        "group_label": "Stage 1",
        "reference_mw": Decimal("100"),
        "current_mw": Decimal("100"),
    }
    defaults.update(overrides)
    return MwAssignmentGroupInput(**defaults)


def synthetic_evaluation_request(**overrides: Any) -> EvaluationRequest:
    """A ready-to-use, minimally-valid `EvaluationRequest` — one MW group
    exactly on target. Every field can be overridden so a test can exercise
    any scenario (multiple groups, missing mw_inputs, different scheme
    types, etc.) without constructing the whole contract by hand."""
    defaults: dict[str, Any] = {
        "scheme_type": SchemeType.UFLS,
        "scheme_version_id": uuid.uuid4(),
        "evaluation_snapshot_id": uuid.uuid4(),
        "topology_version_id": uuid.uuid4(),
        "load_snapshot_id": uuid.uuid4(),
        "trigger": "test",
        "mw_inputs": MwEvaluationInputs(groups=[synthetic_mw_group()]),
    }
    defaults.update(overrides)
    return EvaluationRequest(**defaults)


def synthetic_change_descriptor(**overrides: Any) -> ChangeDescriptor:
    """A ready-to-use, minimally-valid `ChangeDescriptor` (this sprint's
    own instructions §10) — no production source module emits these yet,
    so every test constructs its own via this factory."""
    defaults: dict[str, Any] = {
        "descriptor": "substation_registry.substation.status_changed",
        "source_module": "substation_registry",
        "source_entity_type": "substation",
        "source_entity_id": str(uuid.uuid4()),
        "occurred_at": datetime.now(UTC),
        "reason": "Synthetic test event.",
        "correlation_id": uuid.uuid4(),
    }
    defaults.update(overrides)
    return ChangeDescriptor(**defaults)


class FakeEvaluationRequestProvider(EvaluationRequestProvider):
    """Test fake for `EvaluationRequestProvider` (this sprint's own
    instructions §9: "do not create a production synthetic scheme
    provider"). Returns a fixed, overridable `EvaluationRequest` for
    every call, regardless of `target` — a real future scheme module's
    own provider would instead query its own repository."""

    def __init__(self, request: EvaluationRequest | None = None) -> None:
        self._request = request

    def build_request(self, target: EvaluationTarget, *, trigger: str) -> EvaluationRequest:
        if self._request is not None:
            return self._request
        return synthetic_evaluation_request(
            scheme_type=target.scheme_type,
            scheme_version_id=target.scheme_version_id,
            trigger=trigger,
        )


class RaisingEvaluationRequestProvider(EvaluationRequestProvider):
    """Test fake simulating a provider/input error (this sprint's own
    instructions §22: distinguish provider/input error from detector
    execution error)."""

    def build_request(self, target: EvaluationTarget, *, trigger: str) -> EvaluationRequest:
        raise RuntimeError("synthetic provider failure")


class FakeAffectedSchemeResolver(AffectedSchemeResolver):
    """Test fake for `AffectedSchemeResolver` (this sprint's own
    instructions §13) — returns a fixed, overridable list of targets for
    every event, regardless of the event's own content."""

    def __init__(self, targets: list[EvaluationTarget] | None = None) -> None:
        self._targets = targets if targets is not None else []

    def resolve(self, event: ChangeDescriptor) -> list[EvaluationTarget]:
        return list(self._targets)


class RecordingExecutionEngine:
    """A test double implementing the `ExecutionEngine` protocol that
    *records* every `submit()` call without actually invoking the
    submitted function — used to isolate `request_refresh`'s own
    enqueue/coalescing decisions from the (recursive, immediate) side
    effects real `DirectExecutionEngine` execution would otherwise cause,
    e.g. when testing the generation-mismatch/re-enqueue behaviour in
    isolation (this sprint's own instructions §15-16, §27)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def submit(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        from app.core.execution import ExecutionResult

        self.calls.append({"func": func, "args": args, "kwargs": kwargs})
        return ExecutionResult(
            completed=False, job_id=f"recorded-{len(self.calls)}", result=None, error=None
        )

    def fetch(self, job_id: str) -> Any:
        return None
