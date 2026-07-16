"""`AffectedSchemeResolver` — the typed seam between one platform event
(`ChangeDescriptor`) and the set of `EvaluationTarget`s it may affect
(this sprint's own instructions §13).

No real source-to-scheme mapping exists yet — no scheme module, no shared
cross-reference table. This sprint provides only the interface, a safe
no-op production default (`NullAffectedSchemeResolver`, always zero
targets), and reusable test fakes
(`tests/synthetic_evaluation.py::FakeAffectedSchemeResolver`). A future
real implementation (a shared registry, or aggregation across multiple
scheme modules, per this sprint's own instructions §13) replaces the
default without any change to `ContinuousEvaluationService`'s own
orchestration.

Continuous Evaluation must never know how source entities map to schemes
(CLAUDE.md A1) — no cross-module repository imports, no SQL joins into
future scheme tables live here or anywhere this interface is consumed.
"""

from __future__ import annotations

from typing import Protocol

from app.modules.continuous_evaluation.schemas import ChangeDescriptor, EvaluationTarget


class AffectedSchemeResolver(Protocol):
    def resolve(self, event: ChangeDescriptor) -> list[EvaluationTarget]: ...


class NullAffectedSchemeResolver:
    """The production default until a real shared registry or scheme
    module provides genuine source-to-scheme mapping. Always resolves to
    zero targets — safe, since no source module emits platform events in
    production yet (this sprint's own explicit scope boundary: "existing
    modules will begin emitting events in a later integration sprint")."""

    def resolve(self, event: ChangeDescriptor) -> list[EvaluationTarget]:
        return []
