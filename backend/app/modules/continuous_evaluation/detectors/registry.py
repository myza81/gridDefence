"""Explicit, static detector registration (ADR-022: "explicit static
registration... mirroring the way every existing module registers its own
permission catalog entries" — no dynamic package discovery, no entry
points, no runtime plugin installation, no reflection-based scanning).

`DetectorRegistry` holds explicitly constructed detector instances,
rejects duplicate `detector_id`s, and preserves registration order as the
one deterministic execution order (ADR-022: "execution order carries no
meaning beyond registration order" — there is no additional sort key to
compute, insertion order *is* the deterministic order). Adding a future
detector is one additive `register()` call; nothing here, or in the
engine that consumes this registry, branches on a specific detector's
identity.
"""

from __future__ import annotations

from app.modules.continuous_evaluation.detectors.base import EngineeringFindingDetector
from app.modules.continuous_evaluation.exceptions import DuplicateDetectorIdError
from app.modules.findings_publication_governance.findings import SchemeType


class DetectorRegistry:
    def __init__(self) -> None:
        self._detectors: list[EngineeringFindingDetector] = []
        self._detector_ids: set[str] = set()

    def register(self, detector: EngineeringFindingDetector) -> None:
        if detector.detector_id in self._detector_ids:
            raise DuplicateDetectorIdError(detector.detector_id)
        self._detectors.append(detector)
        self._detector_ids.add(detector.detector_id)

    def for_scheme_type(self, scheme_type: SchemeType) -> list[EngineeringFindingDetector]:
        """Registration-order-preserving filter — the one deterministic
        execution order this sprint's own instructions (§7) require."""
        return [d for d in self._detectors if scheme_type in d.applicable_scheme_types]

    def all(self) -> list[EngineeringFindingDetector]:
        return list(self._detectors)
