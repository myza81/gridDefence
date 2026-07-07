"""EquipmentTopologyMap matching algorithm (psse-integration-module.md §8a;
ADR-006 §8-§9; ADR-007 §6, §9).

A pure function over plain data structures — no ORM objects, no I/O — so it
is fully unit-testable without a database, mirroring `signature.py` and
`raw_parser.py`'s own shape. The service layer adapts real `CircuitTerminal`/
`TopologyBranch`/`TopologyTransformer` rows into `TerminalCandidate`/
`TopologyElementCandidate` before calling this, and persists the results
afterward.

**Matching rule, stated precisely (this is the one genuinely new
implementation detail this phase supplies — the reconciled architecture
docs describe the required *behaviour* [clean-match/unmatched/discrepancy,
mandatory review] but deliberately left the exact algorithm unspecified,
psse-integration-module.md §8a.4):** for a given `CircuitTerminal`, a
candidate PSS/E element is any `TopologyBranch`/`TopologyTransformer` with
one end at this terminal's own substation and the other end at *another*
terminal of the *same* `Circuit`'s substation (this generalizes to tee-off
circuits with no special-casing, exactly as `CircuitTerminal`'s own design
does — equipment-registry-module.md §7.11).

- **Zero candidates** -> `unmatched`.
- **Exactly one candidate whose `ckt_id` matches the `Circuit`'s
  `bay_number`** (case/whitespace-insensitive) -> `clean_match`.
- **Exactly one candidate, but its `ckt_id` does not match `bay_number`**,
  or **more than one candidate exists and none match by `ckt_id`** ->
  `discrepancy` — a plausible correlation exists but cannot be confirmed
  unambiguously, so it is never silently accepted (psse-integration-
  module.md §8a.5: "never silently resolved").
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

MatchOutcome = Literal["clean_match", "unmatched", "discrepancy"]


@dataclass(frozen=True)
class TerminalCandidate:
    circuit_terminal_id: uuid.UUID
    circuit_id: uuid.UUID
    bay_number: str
    substation_id: uuid.UUID


@dataclass(frozen=True)
class TopologyElementCandidate:
    element_type: Literal["branch", "transformer"]
    element_id: int
    from_substation_id: uuid.UUID | None
    to_substation_id: uuid.UUID | None
    ckt_id: str


@dataclass(frozen=True)
class MatchResult:
    circuit_terminal_id: uuid.UUID
    match_outcome: MatchOutcome
    topology_branch_id: int | None
    topology_transformer_id: int | None


def _as_result(
    circuit_terminal_id: uuid.UUID,
    outcome: MatchOutcome,
    element: TopologyElementCandidate | None,
) -> MatchResult:
    if element is None:
        return MatchResult(circuit_terminal_id, outcome, None, None)
    return MatchResult(
        circuit_terminal_id,
        outcome,
        element.element_id if element.element_type == "branch" else None,
        element.element_id if element.element_type == "transformer" else None,
    )


def compute_matches(
    terminals: list[TerminalCandidate],
    elements: list[TopologyElementCandidate],
) -> list[MatchResult]:
    """Computes a match outcome for every supplied terminal. Terminals are
    grouped by `circuit_id` first, since a terminal's candidate elements
    depend on where its *sibling* terminals (same circuit) are located."""
    by_circuit: dict[uuid.UUID, list[TerminalCandidate]] = {}
    for terminal in terminals:
        by_circuit.setdefault(terminal.circuit_id, []).append(terminal)

    results: list[MatchResult] = []
    for circuit_terminals in by_circuit.values():
        substation_ids = {t.substation_id for t in circuit_terminals}
        for terminal in circuit_terminals:
            other_substation_ids = substation_ids - {terminal.substation_id}
            candidates = [
                e
                for e in elements
                if (
                    e.from_substation_id == terminal.substation_id
                    and e.to_substation_id in other_substation_ids
                )
                or (
                    e.to_substation_id == terminal.substation_id
                    and e.from_substation_id in other_substation_ids
                )
            ]
            if not candidates:
                results.append(_as_result(terminal.circuit_terminal_id, "unmatched", None))
                continue

            exact = [
                c
                for c in candidates
                if c.ckt_id.strip().lower() == terminal.bay_number.strip().lower()
            ]
            if len(exact) == 1:
                results.append(_as_result(terminal.circuit_terminal_id, "clean_match", exact[0]))
            elif len(candidates) == 1:
                results.append(
                    _as_result(terminal.circuit_terminal_id, "discrepancy", candidates[0])
                )
            else:
                # Multiple candidates and none (or more than one) match by
                # ckt_id — genuinely ambiguous; never guess.
                results.append(_as_result(terminal.circuit_terminal_id, "discrepancy", None))

    return results
