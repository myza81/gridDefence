"""The detector contract — exactly ADR-022's own `EngineeringFindingDetector`
interface (ADR-022 Decision text: stable `detector_id`; declared
`applicable_scheme_types`; a synchronous `detect(context) -> list[Finding]`
operation).

Detectors are independent (ADR-022): no detector may depend on another
detector's output, execution order carries no engineering meaning beyond
registration order, and a detector must not depend on FastAPI request
state — `detect()` receives only the plain `EvaluationRequest` value
object. Detectors do not persist Findings, do not resolve Publication
Treatment Policy, do not create Publication Records, and do not mutate
scheme or registry data (this sprint's own instructions §6).

An ABC (not a `Protocol`) is used so `detector_id`/`applicable_scheme_types`
are enforced as concrete attributes every subclass must set, matching this
codebase's own preference for explicit, structural contracts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.continuous_evaluation.schemas import EvaluationRequest
from app.modules.findings_publication_governance.findings import Finding, SchemeType


class EngineeringFindingDetector(ABC):
    """One independent, statically-registered detector (ADR-022)."""

    detector_id: str
    applicable_scheme_types: frozenset[SchemeType]

    @abstractmethod
    def detect(self, context: EvaluationRequest) -> list[Finding]:
        """Evaluate `context` and return the (possibly empty) list of
        Findings this detector produces. Must not raise for ordinary
        within-tolerance/no-issue outcomes — only for genuine input/
        configuration failures the detector cannot proceed past."""
        raise NotImplementedError
