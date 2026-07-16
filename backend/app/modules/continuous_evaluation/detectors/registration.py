"""Application composition root for detector registration (ADR-022;
this sprint's own instructions §7, §20: "detectors are registered only
through application composition, never a runtime API").

Only the MW tolerance detector is registered this sprint — no placeholder
detectors for ALSF, Sensitive Customer, topology-change, Boundary Pocket,
cross-scheme overlap, or Critical Infrastructure are registered here
(this sprint's own instructions §7). A future sprint adds its own
detector with one additional `registry.register(...)` call; nothing here
or in `service.py` needs to change shape to accommodate it.
"""

from __future__ import annotations

from app.modules.continuous_evaluation.detectors.mw_tolerance import MwToleranceDetector
from app.modules.continuous_evaluation.detectors.registry import DetectorRegistry
from app.modules.engineering_parameters.service import EngineeringParameterService


def build_default_registry(engineering_parameters: EngineeringParameterService) -> DetectorRegistry:
    registry = DetectorRegistry()
    registry.register(MwToleranceDetector(engineering_parameters))
    return registry
