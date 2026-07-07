"""Deterministic topology signature computation (ADR-003; psse-integration-
module.md §9 rule 4, §10).

The signature is a hash computed **only** over structural connectivity and
rating data — bus/branch/transformer definitions. It never includes load/
generation values or in-service/operational state (which the parser and
persistence layer already keep on entirely separate objects — see
`models.py`'s module docstring — so there is nothing to accidentally
include here even by mistake).

Records are canonicalized before hashing (deterministically sorted, numeric
values normalized to a fixed string representation) so that two
structurally identical files with incidental formatting differences
(record ordering, trailing zeros, scientific-notation vs. plain-decimal
number formatting) produce the same signature — this is the property
ADR-003's own Risk table names first.
"""

from __future__ import annotations

import hashlib

from app.modules.psse_integration.raw_parser import ParsedBranch, ParsedBus, ParsedTransformer


def _fmt(value: float) -> str:
    """Fixed-precision, locale-independent numeric normalization — the
    canonicalization step ADR-003 requires before hashing."""
    return f"{value:.6f}"


def _canonical_bus_line(bus: ParsedBus) -> str:
    # `bus.ide` (PSS/E bus type: 1=load, 2=generator/PV, 3=swing, 4=isolated)
    # is deliberately excluded here — IDE=4 is an in-service/energization
    # flag, not a structural fact, and is already carried as per-snapshot
    # state on `LoadSnapshotBusState.in_service` (service.py). Including it
    # in the topology signature would let a bus's momentary isolated status
    # spuriously produce a "new" TopologyVersion for no structural reason —
    # a real defect fixed by this line's removal (Phase 4.1 stabilization,
    # ADR-003's own exclusion rule).
    return "|".join(
        [
            "BUS",
            str(bus.bus_number),
            _fmt(bus.base_kv),
        ]
    )


def _canonical_branch_line(branch: ParsedBranch) -> str:
    # Order-independent endpoint pair: PSS/E's own from/to assignment is a
    # file-authoring convention, not a structural fact — a branch between
    # bus 100 and bus 200 is the same physical connection regardless of
    # which end was listed first.
    lo, hi = sorted((branch.from_bus, branch.to_bus))
    return "|".join(
        [
            "BRANCH",
            str(lo),
            str(hi),
            branch.ckt_id,
            _fmt(branch.r),
            _fmt(branch.x),
            _fmt(branch.b),
        ]
    )


def _canonical_transformer_line(transformer: ParsedTransformer) -> str:
    lo, hi = sorted((transformer.from_bus, transformer.to_bus))
    tertiary = str(transformer.tertiary_bus) if transformer.tertiary_bus is not None else ""
    return "|".join(
        [
            "TRANSFORMER",
            str(lo),
            str(hi),
            tertiary,
            transformer.ckt_id,
            _fmt(transformer.r),
            _fmt(transformer.x),
        ]
    )


def compute_topology_signature(
    buses: list[ParsedBus],
    branches: list[ParsedBranch],
    transformers: list[ParsedTransformer],
) -> str:
    """Returns a stable SHA-256 hex digest over exactly the structural data
    named above — deterministic regardless of input ordering (CLAUDE.md
    §5.5)."""
    canonical_lines = sorted(_canonical_bus_line(b) for b in buses)
    canonical_lines += sorted(_canonical_branch_line(b) for b in branches)
    canonical_lines += sorted(_canonical_transformer_line(t) for t in transformers)
    canonical_blob = "\n".join(canonical_lines).encode("utf-8")
    return hashlib.sha256(canonical_blob).hexdigest()
