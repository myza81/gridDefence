"""Network Model business errors (CLAUDE.md A9 — structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "NoCurrentTopologyVersionError",
    "SubstationNotFoundError",
    "TopologyVersionNotFoundError",
    "ValidationAppError",
    "VoltageYardNotFoundError",
    "VoltageYardSubstationMismatchError",
]


class SubstationNotFoundError(NotFoundError):
    def __init__(self, substation_id: object) -> None:
        super().__init__(f"Substation {substation_id} not found")


class VoltageYardNotFoundError(NotFoundError):
    """Phase 7F — Operational Snapshot Verification Workspace's optional
    "Starting Switchyard" selection named a `voltage_yard_id` that does not
    exist."""

    def __init__(self, voltage_yard_id: object) -> None:
        super().__init__(f"Voltage yard {voltage_yard_id} not found")


class VoltageYardSubstationMismatchError(ValidationAppError):
    """Phase 7F — the named Switchyard exists but belongs to a different
    Substation than the one requested, so it cannot be used to scope the
    starting seed of a path verification."""

    def __init__(self, voltage_yard_id: object, substation_id: object) -> None:
        super().__init__(
            f"Voltage yard {voltage_yard_id} does not belong to substation {substation_id}"
        )


class TopologyVersionNotFoundError(NotFoundError):
    """Phase 7E — an explicitly-requested `topology_version_id` does not
    exist. Distinct from `NoCurrentTopologyVersionError`: this is a 404
    (a specific, named resource is missing), not a 400 (no default
    resource is available to fall back to)."""

    def __init__(self, topology_version_id: object) -> None:
        super().__init__(f"TopologyVersion {topology_version_id} not found")


class NoCurrentTopologyVersionError(ValidationAppError):
    """Phase 7E — traversal requires an explicit Operational Snapshot
    (Snapshot Awareness requirement) and none was requested, and no
    TopologyVersion is currently Current (e.g. no PSS/E RAW has been
    imported and activated yet). Mirrors `psse_integration`'s own
    exception of the same name/spirit."""

    def __init__(self) -> None:
        super().__init__(
            "No Current TopologyVersion exists to traverse. Import and activate a PSS/E RAW "
            "file first, or specify an explicit topology_version_id."
        )
