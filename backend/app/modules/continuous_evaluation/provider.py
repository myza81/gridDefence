"""`EvaluationRequestProvider` — the typed seam between Continuous
Evaluation and a future scheme module's own repository/assignment data
(this sprint's own instructions §9).

No real scheme module (UFLS/UVLS/EMLS) exists yet, so there is no
production implementation of this interface — only the interface itself,
and reusable synthetic test fakes
(`tests/synthetic_evaluation.py::FakeEvaluationRequestProvider`). A
future scheme module implements `build_request` against its own
repository and registers an instance via `EvaluationRequestProviderRegistry
.register` at its own bootstrap time (mirroring `DetectorRegistry`'s own
explicit, static registration pattern) — nothing here performs dynamic
discovery.

The provider hides scheme repository and assignment details from
Continuous Evaluation entirely: it receives only an opaque
`EvaluationTarget` (scheme type + scheme-version id) and must return the
exact same immutable `EvaluationRequest` Sprint 5's synchronous core
already consumes — never an ORM model, never a scheme-specific shape.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.continuous_evaluation.exceptions import DuplicateProviderRegistrationError
from app.modules.continuous_evaluation.schemas import EvaluationRequest, EvaluationTarget
from app.modules.findings_publication_governance.findings import SchemeType


class EvaluationRequestProvider(Protocol):
    def build_request(self, target: EvaluationTarget, *, trigger: str) -> EvaluationRequest: ...


class EvaluationRequestProviderRegistry:
    """Explicit, static, per-scheme-type registration — empty by default
    in this sprint, since no real scheme module exists yet to register a
    provider. Exactly one provider per scheme type (unlike detectors,
    which may be many per scheme type): a second registration for the
    same scheme type is a composition-time bug, not a runtime condition,
    so it is rejected rather than silently overwritten."""

    def __init__(self) -> None:
        self._providers: dict[SchemeType, EvaluationRequestProvider] = {}

    def register(self, scheme_type: SchemeType, provider: EvaluationRequestProvider) -> None:
        if scheme_type in self._providers:
            raise DuplicateProviderRegistrationError(scheme_type)
        self._providers[scheme_type] = provider

    def get(self, scheme_type: SchemeType) -> EvaluationRequestProvider | None:
        return self._providers.get(scheme_type)


def build_default_provider_registry() -> EvaluationRequestProviderRegistry:
    """No real scheme module exists yet — the production default registry
    is empty. A worker asked to refresh a scheme type with no registered
    provider fails cleanly (`NoEvaluationRequestProviderError`), recorded
    as projection failure metadata, never a crash."""
    return EvaluationRequestProviderRegistry()
