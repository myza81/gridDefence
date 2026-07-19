"""UFLS's own `EvaluationRequestProvider` (continuous_evaluation.provider —
Sprint 6's own typed seam) — the first real, concrete implementation of
that interface, per this sprint's own objective ("The UFLS module must
become the first concrete consumer that validates the platform
abstractions in a real engineering workflow").

**Target MW resolution is fully implemented** — `UflsStage.target_mw` is
always a stored, external-study, engineer-entered value
(shared-defence-scheme-domain-model.md §2); no calculation is ever
performed, only a direct read.

**Current MW resolution is deliberately NOT implemented this phase, and
this provider is NOT registered with Continuous Evaluation's own default
registry.** Resolving "current MW for a given Transformer Terminal (or a
Boundary Pocket's derived isolated island) as of a given LoadSnapshot"
requires correlating that Transformer Terminal (or each island
Substation) to the specific `TopologyBus` carrying its load, then summing
`NetworkLoad` at that bus. That correlation mechanism does not exist for
`TransformerTerminal` today: `EquipmentTopologyMap`
(`psse_integration.models`) is keyed only by `CircuitTerminal`
(boundary-pocket-architecture.md §6 — built specifically for branch/
transformer *connectivity* correlation, not load attribution), and no
equivalent Transformer-Terminal-or-Substation-to-Bus load correlation is
documented anywhere in this pack.

Per this sprint's own explicit instruction — "If the Continuous
Evaluation architecture requires a separate later implementation sprint,
implement only the stable contracts and documented registration points
now, and clearly report what remains deferred" — this module implements
the correct, complete *contract* (this class, its target-MW resolution,
and its registration point) without inventing a new, speculative
cross-module load-correlation mechanism that no authoritative document
describes. See the completion report's own "Continuous Evaluation
integration summary" and "Deferred items" sections for the full
reasoning; this is not a silently-skipped requirement.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.modules.continuous_evaluation.exceptions import AppError
from app.modules.continuous_evaluation.provider import EvaluationRequestProvider
from app.modules.continuous_evaluation.schemas import (
    EvaluationRequest,
    EvaluationTarget,
    MwAssignmentGroupInput,
    MwEvaluationInputs,
)
from app.modules.ufls.repository import UflsRepository
from app.modules.ufls.service import UflsService


class CurrentMwNotResolvableError(AppError):
    """Raised by `UflsEvaluationRequestProvider.build_request` — see this
    module's own docstring. Deliberate, documented, not a bug: no
    Transformer-Terminal/Substation-to-Bus load correlation mechanism is
    established anywhere in this pack yet."""

    def __init__(self) -> None:
        super().__init__(
            "UFLS current-MW resolution is not yet implemented — no "
            "Transformer-Terminal/Substation-to-Bus load correlation mechanism exists "
            "in PSS/E Integration or Network Model today. See "
            "docs/architecture/ufls-architecture.md for the full deferral rationale.",
            code="ufls_current_mw_not_resolvable",
        )


class UflsEvaluationRequestProvider(EvaluationRequestProvider):
    """Builds the `EvaluationRequest` a future background refresh (or a
    direct synchronous call) would pass to
    `ContinuousEvaluationService.evaluate`. Target MW is always resolved
    correctly; current MW raises `CurrentMwNotResolvableError` — see this
    module's own docstring."""

    def __init__(self, db) -> None:
        self._db = db
        self._ufls = UflsService(db)
        self._repo = UflsRepository(db)

    def build_request(self, target: EvaluationTarget, *, trigger: str) -> EvaluationRequest:
        version = self._ufls.get_version(target.scheme_version_id)
        stages = self._repo.list_stages(version.version_id)

        groups = []
        for stage in stages:
            if stage.target_mw is None:
                continue
            groups.append(
                MwAssignmentGroupInput(
                    group_id=str(stage.ufls_stage_id),
                    group_label=f"UFLS Stage {stage.ufls_stage_id}",
                    reference_mw=Decimal(str(stage.target_mw)),
                    current_mw=self._resolve_current_mw(stage.ufls_stage_id),
                )
            )

        return EvaluationRequest(
            scheme_type=target.scheme_type,
            scheme_version_id=target.scheme_version_id,
            topology_version_id=version.topology_version_id,
            load_snapshot_id=version.load_snapshot_id,
            trigger=trigger,
            mw_inputs=MwEvaluationInputs(groups=groups) if groups else None,
        )

    def _resolve_current_mw(self, ufls_stage_id: uuid.UUID) -> Decimal:
        raise CurrentMwNotResolvableError()


def register_provider(registry, db) -> None:
    """The documented registration point this sprint's own instructions
    ask for ("implement only the stable contracts and documented
    registration points now"). Not called from any composition root
    today: `ContinuousEvaluationService.__init__`
    (`continuous_evaluation/service.py`) still only ever builds its own
    empty `build_default_provider_registry()` — there is no existing
    application-startup or worker-startup hook anywhere in this codebase
    that assembles a shared, pre-populated
    `EvaluationRequestProviderRegistry` and passes it in (the same is
    true of `DetectorRegistry`'s own `build_default_registry`, which is
    likewise never called from `main.py`). Wiring this call in is
    Continuous Evaluation's own composition-root work, not something a
    single scheme module should invent unilaterally; see the completion
    report's "Continuous Evaluation integration summary" for the full
    reasoning. A future caller registers this provider with:

        from app.modules.ufls.evaluation import register_provider
        register_provider(service.provider_registry, db)
    """
    from app.modules.findings_publication_governance.findings import SchemeType

    registry.register(SchemeType.UFLS, UflsEvaluationRequestProvider(db))
