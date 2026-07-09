"""Tests for Operational Bus classification (bus_classification.py;
EDR-007 §4; Phase 7A). A pure naming-pattern classifier — no database, no
correlation decision — so these tests exercise `classify_bus_name`
directly against representative names, including the real ones observed
during the EDR-007 discovery (docs/samples/psse/110226n.raw)."""

from __future__ import annotations

import pytest

from app.modules.psse_integration.bus_classification import classify_bus_name


@pytest.mark.parametrize(
    "bus_name",
    ["ABBA132", "KLGT275", "BDKY500", "PKLG132"],
)
def test_switchyard_bus_naming_convention(bus_name: str) -> None:
    assert classify_bus_name(bus_name) == "SWITCHYARD_BUS"


@pytest.mark.parametrize(
    "bus_name",
    ["BLPS132L", "BLPS132R"],
)
def test_split_switchyard_bus_naming_convention(bus_name: str) -> None:
    assert classify_bus_name(bus_name) == "SPLIT_SWITCHYARD_BUS"


@pytest.mark.parametrize("bus_name", [None, "", "   "])
def test_blank_named_bus(bus_name: str | None) -> None:
    assert classify_bus_name(bus_name) == "BLANK_NAMED_BUS"


@pytest.mark.parametrize(
    "bus_name",
    ["TJGSM1A", "TJGSM1B", "SDAOFIC", "LMTMFIC", "ATWRFIC", "BPHEFIC1", "SRYAFIC2"],
)
def test_fictitious_bus(bus_name: str) -> None:
    assert classify_bus_name(bus_name) == "FICTITIOUS_BUS"


@pytest.mark.parametrize(
    "bus_name",
    ["NURGT1A", "PKLPGT13", "JMHE_U1"],
)
def test_other_non_conforming_bus(bus_name: str) -> None:
    assert classify_bus_name(bus_name) == "OTHER_NON_CONFORMING_BUS"


def test_fictitious_check_never_overrides_a_well_formed_switchyard_match() -> None:
    """A mnemonic that happens to contain the substring "FIC" but still
    matches the well-formed 4-letter-mnemonic + voltage pattern must be
    classified as a Switchyard Bus, not misclassified as Fictitious — the
    positive naming-convention match takes precedence (module docstring)."""
    assert classify_bus_name("XFIC132") == "SWITCHYARD_BUS"


def test_classification_is_case_insensitive_for_the_fictitious_check() -> None:
    assert classify_bus_name("tjgsm1a") == "FICTITIOUS_BUS"
    assert classify_bus_name("sdaofic") == "FICTITIOUS_BUS"


def test_classification_is_deterministic() -> None:
    """The same name always classifies the same way — no randomness, no
    hidden state, no database dependency."""
    for _ in range(5):
        assert classify_bus_name("ABBA132") == "SWITCHYARD_BUS"


def test_real_sample_file_bus_classification_counts() -> None:
    """End-to-end confirmation against the real sample RAW file used
    throughout the EDR-007 discovery — the exact counts already confirmed
    during that investigation."""
    from pathlib import Path

    from app.modules.psse_integration.raw_parser import parse_raw

    sample_path = Path(__file__).resolve().parents[5] / "docs" / "samples" / "psse" / "110226n.raw"
    assert sample_path.exists(), f"Sample file not found: {sample_path}"
    case = parse_raw(sample_path.read_text(encoding="utf-8", errors="replace"))

    counts: dict[str, int] = {}
    for bus in case.buses:
        counts[bus.bus_classification] = counts.get(bus.bus_classification, 0) + 1

    assert counts["FICTITIOUS_BUS"] == 9
    assert counts["SWITCHYARD_BUS"] == 731
    assert counts["SPLIT_SWITCHYARD_BUS"] == 58
    assert counts["BLANK_NAMED_BUS"] == 468
    assert counts["OTHER_NON_CONFORMING_BUS"] == 254
    assert sum(counts.values()) == len(case.buses)
