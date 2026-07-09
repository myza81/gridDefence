"""Tests for the PSS/E RAW parser (raw_parser.py), including integration
tests against the real reference sample files at `docs/samples/psse/` (this
phase's explicit mandate: design and verify against real files, not
generic documentation). The samples are read directly from the repository,
never copied into the backend tree.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.psse_integration.raw_parser import (
    ParsedCase,
    RawParseError,
    parse_raw,
)

_SAMPLES_DIR = Path(__file__).resolve().parents[5] / "docs" / "samples" / "psse"
_FULL_TOPOLOGY_FILE = _SAMPLES_DIR / "110226n.raw"
_LOAD_ONLY_FILE = _SAMPLES_DIR / "PSSE_LOAD_20260608_1730.raw"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def full_topology_case() -> ParsedCase:
    assert _FULL_TOPOLOGY_FILE.exists(), f"Sample file not found: {_FULL_TOPOLOGY_FILE}"
    return parse_raw(_read(_FULL_TOPOLOGY_FILE))


@pytest.fixture(scope="module")
def load_only_case() -> ParsedCase:
    assert _LOAD_ONLY_FILE.exists(), f"Sample file not found: {_LOAD_ONLY_FILE}"
    return parse_raw(_read(_LOAD_ONLY_FILE))


# --- Full topology + load sample (110226n.raw) --------------------------------------


def test_full_topology_file_is_detected_as_full_topology(full_topology_case: ParsedCase) -> None:
    assert full_topology_case.is_full_topology is True


def test_full_topology_file_parses_a_substantial_bus_count(
    full_topology_case: ParsedCase,
) -> None:
    # Real, observed count from this sample file (verified during the
    # mandatory pre-implementation inspection) — asserting a floor, not an
    # exact count, so the test survives if the shared sample file is
    # regenerated with a similar-sized case.
    assert len(full_topology_case.buses) > 1000


def test_full_topology_file_parses_branches_and_transformers(
    full_topology_case: ParsedCase,
) -> None:
    assert len(full_topology_case.branches) > 0
    assert len(full_topology_case.transformers) > 0


def test_full_topology_file_parses_both_two_and_three_winding_transformers(
    full_topology_case: ParsedCase,
) -> None:
    two_winding = [t for t in full_topology_case.transformers if t.tertiary_bus is None]
    three_winding = [t for t in full_topology_case.transformers if t.tertiary_bus is not None]
    assert two_winding, "Expected at least one 2-winding transformer"
    assert three_winding, "Expected at least one 3-winding transformer"


def test_full_topology_file_parses_loads_and_generators(full_topology_case: ParsedCase) -> None:
    assert len(full_topology_case.loads) > 0
    assert len(full_topology_case.generators) > 0


def test_full_topology_file_parses_load_owner(full_topology_case: ParsedCase) -> None:
    """Phase 7A (EDR-007 §7.3) — PSS/E's own Owner field is parsed for
    every Load record in this file's standard 17-field shape; none are
    left `None`, since this sample has no abbreviated-shape records."""
    assert full_topology_case.loads, "Expected at least one load record"
    assert all(load.owner is not None for load in full_topology_case.loads)
    # Real, observed value from the sample file's first load record.
    assert full_topology_case.loads[0].owner == 5


def test_full_topology_file_extracts_voltage_solution_on_buses(
    full_topology_case: ParsedCase,
) -> None:
    with_voltage = [b for b in full_topology_case.buses if b.voltage_mag is not None]
    assert with_voltage, "Expected at least one bus with a parsed voltage magnitude"


def test_full_topology_file_produces_no_unparseable_load_warnings(
    full_topology_case: ParsedCase,
) -> None:
    assert not any("Could not parse" in w for w in full_topology_case.warnings)


# --- Header metadata (Phase 7 discovery-support enhancement) -------------------------


def test_full_topology_file_extracts_header_metadata(full_topology_case: ParsedCase) -> None:
    """Real, observed values from this sample file's own header line
    (`0,   100.00, 34,     0,     1, 50.00     / PSS(R)E 34 RAW created by
    rawd34  WED, FEB 11 2026  14:43`) and its two case-identification title
    lines (`OPERATION STUDY`, `CPF_03 JAN 2025`)."""
    assert full_topology_case.rev == 34
    assert full_topology_case.sbase == 100.0
    assert full_topology_case.frequency_hz == 50.0
    assert full_topology_case.case_description == "CPF_03 JAN 2025"
    assert full_topology_case.raw_created == "WED, FEB 11 2026 14:43"


def test_full_topology_file_raw_created_is_the_export_note_not_the_study_date(
    full_topology_case: ParsedCase,
) -> None:
    """ "RAW Created" must reflect the RAW writer's own export timestamp
    (from the header line's trailing comment), never the case-identification
    title lines' own study-date text — these are two distinct facts even
    though both happen to mention a date in this sample file."""
    assert full_topology_case.raw_created != full_topology_case.case_description
    assert "2026" in (full_topology_case.raw_created or "")


def test_full_topology_signature_is_stable_across_reparse() -> None:
    """Re-parsing the same byte-identical file must produce byte-identical
    `ParsedBus`/`ParsedBranch`/`ParsedTransformer` data (a precondition for
    the topology signature actually being deterministic — see
    test_signature.py for the hashing behaviour itself)."""
    from app.modules.psse_integration.signature import compute_topology_signature

    content = _read(_FULL_TOPOLOGY_FILE)
    case1 = parse_raw(content)
    case2 = parse_raw(content)
    sig1 = compute_topology_signature(case1.buses, case1.branches, case1.transformers)
    sig2 = compute_topology_signature(case2.buses, case2.branches, case2.transformers)
    assert sig1 == sig2


# --- Load-only sample (PSSE_LOAD_20260608_1730.raw) ----------------------------------


def test_load_only_file_is_detected_as_load_only(load_only_case: ParsedCase) -> None:
    assert load_only_case.is_full_topology is False
    assert len(load_only_case.buses) == 0


def test_load_only_file_parses_load_records(load_only_case: ParsedCase) -> None:
    assert len(load_only_case.loads) > 0


def test_load_only_file_has_no_load_owner(load_only_case: ParsedCase) -> None:
    """Phase 7A (EDR-007 §7.3) — the load-only sample uses the abbreviated
    7-field LOAD DATA shape, which has no OWNER field at all; `owner` must
    gracefully be `None`, never a parse failure."""
    assert load_only_case.loads
    assert all(load.owner is None for load in load_only_case.loads)


def test_load_only_file_handles_no_reading_records_as_warnings_not_errors(
    load_only_case: ParsedCase,
) -> None:
    """The abbreviated load-only sample contains real ' / No Reading /'
    records (a meter with no reading that cycle) — these are valid,
    meaningful records, not malformed data, and must not be reported as
    generic parse failures."""
    assert any("no reading" in w.lower() for w in load_only_case.warnings)
    assert not any("could not parse" in w.lower() for w in load_only_case.warnings)


def test_load_only_file_has_no_branches_or_transformers(load_only_case: ParsedCase) -> None:
    assert load_only_case.branches == []
    assert load_only_case.transformers == []


def test_load_only_file_has_no_header_metadata(load_only_case: ParsedCase) -> None:
    """The load-only sample has zero header lines at all (module docstring
    point 2) — every header metadata field must gracefully be `None`, never
    a parse failure (Phase 7 discovery-support enhancement)."""
    assert load_only_case.frequency_hz is None
    assert load_only_case.case_description is None
    assert load_only_case.raw_created is None


# --- Load Owner (Phase 7A, module docstring point 6) --------------------------------


def test_standard_shape_load_record_parses_owner_from_field_11() -> None:
    content = (
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\n"
        "123,'1',1,1,1,10.0,5.0,0.0,0.0,0.0,0.0,99,1,0,0.0,0.0,0\n"
        "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\n"
        "Q\n"
    )
    case = parse_raw(content)
    assert len(case.loads) == 1
    assert case.loads[0].owner == 99


def test_abbreviated_shape_load_record_has_no_owner() -> None:
    content = (
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\n"
        "  123,'1 ',1,   1,   1,   10.0,   5.0\n"
        "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\n"
        "Q\n"
    )
    case = parse_raw(content)
    assert len(case.loads) == 1
    assert case.loads[0].owner is None


# --- Robustness / extensibility (module docstring points 1-4) -----------------------


def test_unknown_section_name_produces_a_warning_not_a_crash() -> None:
    content = (
        "0 / END OF SOME FUTURE UNKNOWN SECTION, BEGIN LOAD DATA\n"
        "  123,'1 ',1,   1,   1,   10.0,   5.0\n"
        "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\n"
        "Q\n"
    )
    case = parse_raw(content)
    assert len(case.loads) == 1
    assert case.loads[0].bus_number == 123


def test_absent_case_identification_header_does_not_error() -> None:
    """The load-only sample has zero header lines — `rev`/`sbase` must be
    optional, never required for a successful parse (module docstring
    point 2)."""
    content = "0 / END OF LOAD DATA, BEGIN GENERATOR DATA\nQ\n"
    case = parse_raw(content)
    assert case.rev is None
    assert case.sbase is None
    assert case.warnings is not None  # never raises


def test_header_present_but_title_lines_absent_yields_null_case_description() -> None:
    """A header line immediately followed by a terminator (no title lines
    at all) must not error — `case_description` is simply `None` (module
    docstring point 5), same best-effort rule as `rev`/`sbase`."""
    content = (
        "0,   100.00, 34,     0,     1, 50.00\n"
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\nQ\n"
    )
    case = parse_raw(content)
    assert case.rev == 34
    assert case.frequency_hz == 50.0
    assert case.case_description is None
    assert case.raw_created is None


def test_header_comment_from_an_unrecognized_writer_tool_yields_null_raw_created() -> None:
    """A header comment that doesn't match this project's one observed RAW
    writer's wording must gracefully yield `None`, never a parse failure or
    a guessed value (module docstring point 5)."""
    content = (
        "0,   100.00, 34,     0,     1, 50.00     / Exported by SomeOtherTool v2\n"
        "OPERATION STUDY\n"
        "TEST CASE\n"
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\nQ\n"
    )
    case = parse_raw(content)
    assert case.raw_created is None
    assert case.case_description == "TEST CASE"


def test_missing_second_title_line_falls_back_to_first_title_line() -> None:
    """Only one case-identification title line present before the
    terminator — `case_description` falls back to it rather than staying
    `None` (module docstring point 5)."""
    content = (
        "0,   100.00, 34,     0,     1, 50.00\n"
        "GENERAL STUDY DESCRIPTION\n"
        "0 / END OF SYSTEM-WIDE DATA, BEGIN BUS DATA\n"
        "0 / END OF BUS DATA, BEGIN LOAD DATA\nQ\n"
    )
    case = parse_raw(content)
    assert case.case_description == "GENERAL STUDY DESCRIPTION"


def test_empty_content_raises_raw_parse_error() -> None:
    with pytest.raises(RawParseError):
        parse_raw("")


def test_garbage_content_is_tolerated_not_fatal() -> None:
    """Unrecognized content is treated as an unknown section's data (module
    docstring point 1) — never a hard parse failure, since a non-empty file
    with no terminator lines at all is simply a single (unknown) section."""
    case = parse_raw("this is not a real PSS/E file at all\nneither is this line\n")
    assert case.buses == []
    assert case.loads == []
