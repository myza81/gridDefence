"""Tests for the EquipmentTopologyMap matching algorithm (matching.py;
ADR-006 §8-§9; ADR-007 §6, §9)."""

from __future__ import annotations

import uuid

from app.modules.psse_integration.matching import (
    TerminalCandidate,
    TopologyElementCandidate,
    compute_matches,
)

_CIRCUIT_A = uuid.uuid4()
_TERMINAL_1 = uuid.uuid4()
_TERMINAL_2 = uuid.uuid4()
_TERMINAL_3 = uuid.uuid4()
_SUBSTATION_PKLG = uuid.uuid4()
_SUBSTATION_IGBK = uuid.uuid4()
_SUBSTATION_NKST = uuid.uuid4()


def test_two_terminal_circuit_with_matching_ckt_id_is_clean_match() -> None:
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
    ]
    elements = [
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "1"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "clean_match"
    assert results[_TERMINAL_1].topology_branch_id == 1
    assert results[_TERMINAL_2].match_outcome == "clean_match"


def test_no_candidate_element_is_unmatched() -> None:
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
    ]
    results = compute_matches(terminals, [])
    assert all(r.match_outcome == "unmatched" for r in results)
    assert all(r.topology_branch_id is None for r in results)


def test_candidate_with_mismatched_ckt_id_is_discrepancy() -> None:
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
    ]
    elements = [
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "2"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "discrepancy"
    assert results[_TERMINAL_1].topology_branch_id == 1


def test_ckt_id_match_is_case_and_whitespace_insensitive() -> None:
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, " L1 ", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, " L1 ", _SUBSTATION_IGBK),
    ]
    elements = [
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "l1"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "clean_match"


def test_multiple_candidates_with_no_exact_ckt_id_match_is_discrepancy_never_guessed() -> None:
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
    ]
    elements = [
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "2"),
        TopologyElementCandidate("transformer", 5, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "3"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "discrepancy"
    # Ambiguous — never picks one of the multiple candidates.
    assert results[_TERMINAL_1].topology_branch_id is None
    assert results[_TERMINAL_1].topology_transformer_id is None


def test_multiple_candidates_with_exactly_one_exact_ckt_id_match_is_clean_match() -> None:
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
    ]
    elements = [
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "1"),
        TopologyElementCandidate("transformer", 5, _SUBSTATION_PKLG, _SUBSTATION_IGBK, "9"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "clean_match"
    assert results[_TERMINAL_1].topology_branch_id == 1


def test_teeoff_circuit_generalizes_without_special_casing() -> None:
    """A three-terminal tee-off circuit: each terminal's candidates are
    elements connecting it to *either other* terminal's substation."""
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
        TerminalCandidate(_TERMINAL_3, _CIRCUIT_A, "1", _SUBSTATION_NKST),
    ]
    elements = [
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, _SUBSTATION_NKST, "1"),
        TopologyElementCandidate("branch", 2, _SUBSTATION_IGBK, _SUBSTATION_NKST, "1"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "clean_match"
    assert results[_TERMINAL_1].topology_branch_id == 1
    assert results[_TERMINAL_2].match_outcome == "clean_match"
    assert results[_TERMINAL_2].topology_branch_id == 2
    # NKST's own terminal has two valid candidates (one to each other
    # terminal), neither of which is wrong — but since two distinct
    # elements both carry the same ckt_id "1", there are two "exact"
    # matches, which is still ambiguous for *this* terminal specifically.
    assert results[_TERMINAL_3].match_outcome == "discrepancy"


def test_different_circuits_do_not_share_candidates() -> None:
    """A terminal on Circuit A must never match an element that only
    connects to a Circuit B substation."""
    circuit_b = uuid.uuid4()
    terminal_b = uuid.uuid4()
    substation_other = uuid.uuid4()
    terminals = [
        TerminalCandidate(_TERMINAL_1, _CIRCUIT_A, "1", _SUBSTATION_PKLG),
        TerminalCandidate(_TERMINAL_2, _CIRCUIT_A, "1", _SUBSTATION_IGBK),
        TerminalCandidate(terminal_b, circuit_b, "1", _SUBSTATION_PKLG),
    ]
    elements = [
        # Connects PKLG to a substation that is only on Circuit B's side —
        # not a valid candidate for Circuit A's PKLG terminal.
        TopologyElementCandidate("branch", 1, _SUBSTATION_PKLG, substation_other, "1"),
    ]
    results = {r.circuit_terminal_id: r for r in compute_matches(terminals, elements)}
    assert results[_TERMINAL_1].match_outcome == "unmatched"
    assert results[_TERMINAL_2].match_outcome == "unmatched"
