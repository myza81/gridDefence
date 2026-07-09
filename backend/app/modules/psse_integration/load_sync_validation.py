"""Load-only Snapshot Synchronisation validation (Phase 7B).

Governing references: EDR-007's Engineering Principle 12 (Operational
Identity Persistence — Bus Number is the authoritative Operational
Identity); `operational-snapshot-architecture.md` §9 (Topology
Independence — "Operational Topology shall not be implicitly redefined by
incremental operational datasets"); ADR-003's Load-only Update Workflow.

Core Rule: a load-only RAW file must not redefine Operational Topology. It
synchronises against the currently active topology using Bus Number as the
sole correlation key. This module never creates, updates, or infers
`TopologyVersion`/`TopologyBus` rows — it only compares already-known data
and reports findings for engineering review (never resolved automatically —
`operational-snapshot-architecture.md` §8). Pure functions and dataclasses
only — no database access, no ORM, mirroring `bus_classification.py`'s and
`matching.py`'s own established style.

A genuine load-only RAW file (the only shape observed in this project's own
sample, `PSSE_LOAD_20260608_1730.raw` — see `raw_parser.py`'s module
docstring) carries zero BUS DATA records, so it can never itself supply a
Bus Name or nominal voltage to compare. `incoming_bus_references` below is
therefore empty in every currently-observed real file, and identity
mismatch detection (validate identity across Bus Number) will correctly
find nothing to compare — this is expected, not a defect. The check is
still implemented and exercised directly (via synthetic fixtures, per this
phase's own testing guidance) so that a future load-only-like variant that
does carry reference Bus identity data is handled correctly without further
code changes, per EDR-007's Core Rule ("do not automatically reinterpret
the bus" — flag, never guess).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActiveTopologyBusRef:
    """The minimal identity facts already persisted on `TopologyBus`,
    needed for synchronisation comparison — never the full ORM row, so
    this module stays decoupled from persistence (mirrors
    `TerminalCandidate`/`TopologyElementCandidate` in `matching.py`)."""

    bus_number: int
    bus_name: str | None
    base_kv: float


@dataclass(frozen=True)
class BusIdentityMismatch:
    """A Bus Number present on both sides with a differing Bus Name and/or
    nominal voltage. Reported for engineering review — never auto-resolved,
    never treated as evidence the bus should be reinterpreted."""

    bus_number: int
    active_bus_name: str | None
    incoming_bus_name: str | None
    active_base_kv: float
    incoming_base_kv: float
    mismatch_reason: str  # "bus_name" | "base_kv" | "bus_name,base_kv"


@dataclass(frozen=True)
class LoadSyncValidationResult:
    total_load_records: int
    total_distinct_load_buses: int
    matched_load_buses: int
    unmatched_load_bus_numbers: list[int]
    missing_topology_bus_numbers: list[int]
    identity_mismatches: list[BusIdentityMismatch]


def _identity_differs(active: ActiveTopologyBusRef, incoming: ActiveTopologyBusRef) -> str | None:
    name_differs = (incoming.bus_name or "").strip().upper() != (
        active.bus_name or ""
    ).strip().upper()
    voltage_differs = incoming.base_kv != active.base_kv
    if not name_differs and not voltage_differs:
        return None
    if name_differs and voltage_differs:
        return "bus_name,base_kv"
    return "bus_name" if name_differs else "base_kv"


def validate_load_only_synchronization(
    *,
    load_bus_numbers: list[int],
    active_topology_buses: list[ActiveTopologyBusRef],
    previously_loaded_bus_numbers: set[int] | None = None,
    incoming_bus_references: list[ActiveTopologyBusRef] | None = None,
) -> LoadSyncValidationResult:
    """Compares a load-only case's load records against the active
    topology's own bus records, correlated exclusively by Bus Number.

    - `load_bus_numbers`: one entry per parsed load record (not
      deduplicated — needed to report `total_load_records` faithfully).
    - `active_topology_buses`: the active `TopologyVersion`'s own bus
      identity, already persisted — never written to by this function.
    - `previously_loaded_bus_numbers`: the bus numbers that had a load in
      the topology's previously Current `LoadSnapshot`, if any — the safe,
      already-known signal for "a topology bus expected to have load but
      absent from this file" (§ requirement 2). `None`/empty means no
      prior load snapshot exists to compare against.
    - `incoming_bus_references`: this case's own Bus Number/Name/voltage
      records, if the file happens to carry any (see module docstring).
    """
    active_by_number = {bus.bus_number: bus for bus in active_topology_buses}
    distinct_load_buses = sorted(set(load_bus_numbers))

    unmatched_load_bus_numbers = [n for n in distinct_load_buses if n not in active_by_number]
    matched_load_buses = len(distinct_load_buses) - len(unmatched_load_bus_numbers)

    missing_topology_bus_numbers: list[int] = []
    if previously_loaded_bus_numbers:
        distinct_load_bus_set = set(distinct_load_buses)
        missing_topology_bus_numbers = sorted(
            n for n in previously_loaded_bus_numbers if n not in distinct_load_bus_set
        )

    identity_mismatches: list[BusIdentityMismatch] = []
    if incoming_bus_references:
        incoming_by_number = {bus.bus_number: bus for bus in incoming_bus_references}
        for number, active_bus in active_by_number.items():
            incoming_bus = incoming_by_number.get(number)
            if incoming_bus is None:
                continue
            reason = _identity_differs(active_bus, incoming_bus)
            if reason is None:
                continue
            identity_mismatches.append(
                BusIdentityMismatch(
                    bus_number=number,
                    active_bus_name=active_bus.bus_name,
                    incoming_bus_name=incoming_bus.bus_name,
                    active_base_kv=active_bus.base_kv,
                    incoming_base_kv=incoming_bus.base_kv,
                    mismatch_reason=reason,
                )
            )

    return LoadSyncValidationResult(
        total_load_records=len(load_bus_numbers),
        total_distinct_load_buses=len(distinct_load_buses),
        matched_load_buses=matched_load_buses,
        unmatched_load_bus_numbers=unmatched_load_bus_numbers,
        missing_topology_bus_numbers=missing_topology_bus_numbers,
        identity_mismatches=identity_mismatches,
    )
