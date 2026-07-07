"""Tests for the deterministic topology signature (signature.py; ADR-003)."""

from __future__ import annotations

from app.modules.psse_integration.raw_parser import ParsedBranch, ParsedBus, ParsedTransformer
from app.modules.psse_integration.signature import compute_topology_signature


def _bus(number: int, kv: float = 132.0, ide: int = 1) -> ParsedBus:
    return ParsedBus(
        bus_number=number, bus_name=f"BUS{number}", base_kv=kv, ide=ide, area=1, zone=1, owner=1
    )


def _branch(from_bus: int, to_bus: int, ckt: str = "1") -> ParsedBranch:
    return ParsedBranch(
        from_bus=from_bus,
        to_bus=to_bus,
        ckt_id=ckt,
        r=0.001,
        x=0.01,
        b=0.0002,
        rate_a=100.0,
        rate_b=None,
        rate_c=None,
        status=True,
    )


def _transformer(from_bus: int, to_bus: int, tertiary: int | None = None) -> ParsedTransformer:
    return ParsedTransformer(
        from_bus=from_bus,
        to_bus=to_bus,
        tertiary_bus=tertiary,
        ckt_id="1",
        r=0.002,
        x=0.05,
        rate_a=200.0,
        status=True,
    )


def test_same_structural_data_produces_same_signature() -> None:
    buses = [_bus(100), _bus(200)]
    branches = [_branch(100, 200)]
    sig1 = compute_topology_signature(buses, branches, [])
    sig2 = compute_topology_signature(list(buses), list(branches), [])
    assert sig1 == sig2


def test_record_order_does_not_affect_signature() -> None:
    buses = [_bus(100), _bus(200), _bus(300)]
    branches = [_branch(100, 200), _branch(200, 300)]
    forward = compute_topology_signature(buses, branches, [])
    reversed_order = compute_topology_signature(list(reversed(buses)), list(reversed(branches)), [])
    assert forward == reversed_order


def test_branch_endpoint_order_does_not_affect_signature() -> None:
    """PSS/E's own from/to assignment is a file-authoring convention, not a
    structural fact (signature.py's own stated rationale)."""
    buses = [_bus(100), _bus(200)]
    forward = compute_topology_signature(buses, [_branch(100, 200)], [])
    backward = compute_topology_signature(buses, [_branch(200, 100)], [])
    assert forward == backward


def test_transformer_endpoint_order_does_not_affect_signature() -> None:
    buses = [_bus(100), _bus(200)]
    forward = compute_topology_signature(buses, [], [_transformer(100, 200)])
    backward = compute_topology_signature(buses, [], [_transformer(200, 100)])
    assert forward == backward


def test_different_impedance_changes_signature() -> None:
    buses = [_bus(100), _bus(200)]
    base = compute_topology_signature(buses, [_branch(100, 200)], [])
    changed_branch = _branch(100, 200)
    changed_branch.r = 0.999
    changed = compute_topology_signature(buses, [changed_branch], [])
    assert base != changed


def test_different_bus_set_changes_signature() -> None:
    sig_two_buses = compute_topology_signature([_bus(100), _bus(200)], [], [])
    sig_three_buses = compute_topology_signature([_bus(100), _bus(200), _bus(300)], [], [])
    assert sig_two_buses != sig_three_buses


def test_signature_is_a_sha256_hex_digest() -> None:
    signature = compute_topology_signature([_bus(100)], [], [])
    assert len(signature) == 64
    int(signature, 16)  # raises ValueError if not valid hex


def test_bus_ide_does_not_affect_signature() -> None:
    """Phase 4.1 stabilization: IDE (PSS/E bus type; 4 = isolated/out-of-
    service) is operational state, not structural identity (ADR-003) — a
    bus temporarily isolated in one snapshot and back in-service in the
    next must not register as a structurally different topology."""
    normal = compute_topology_signature([_bus(100, ide=1)], [], [])
    swing = compute_topology_signature([_bus(100, ide=3)], [], [])
    isolated = compute_topology_signature([_bus(100, ide=4)], [], [])
    assert normal == swing == isolated
