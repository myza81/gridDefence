"""PSS/E RAW file parser.

Design reverse-engineered directly from the two reference sample files at
`docs/samples/psse/` (per this phase's explicit mandate to design against
real files, not generic documentation), not from an abstract spec:

- **`110226n.raw`** — a full topology+load snapshot, PSS/E RAW rev 34.
  Standard case-identification header (`IC,SBASE,REV,...`), then sections in
  the usual rev-34 order (BUS, LOAD, FIXED SHUNT, GENERATOR, BRANCH, SYSTEM
  SWITCHING DEVICE, TRANSFORMER, ...), each ended by a
  `0 / END OF <X> DATA, BEGIN <Y> DATA` terminator line. Transformer records
  are 4 lines (2-winding) or 5 lines (3-winding) — this file contains both.
- **`PSSE_LOAD_20260608_1730.raw`** — a load-only snapshot with **no header
  at all** (the file starts directly at the first terminator line), **zero
  bus records**, and LOAD DATA records in an **abbreviated 7-field shape**
  (`I,'ID',STAT,,,PL,QL` — blank AREA/ZONE, no IP/IQ/YP/YQ/OWNER/SCALE/
  INTRPT/DGEN* fields at all) with a trailing free-text `/ comment`. Every
  section after LOAD DATA is empty, and the terminator labels themselves are
  inconsistent/out of the rev-34 sequence (e.g. section names that don't
  appear in the first file at all) — this is real, observed behaviour, not
  a hypothetical edge case.

**Consequences for this parser's design, directly driven by the above:**

1. Section boundaries are tracked purely by counting `0 / END OF ...`
   terminator lines in the order they appear — never by matching against a
   fixed, closed list of expected section names. An unrecognized section
   name is tolerated (its data lines are skipped with a warning), not an
   error. This is what "extensible for future PSS/E RAW revisions" means
   concretely: a new section type, or a differently-worded terminator,
   never breaks parsing of the sections this module actually understands.
2. The case-identification header may be **entirely absent** (zero lines
   before the first terminator) — `rev`/`sbase` are optional, best-effort
   metadata, never required for a successful parse.
3. LOAD DATA records are parsed **by field count, not by a fixed
   position/format** — 17+ fields is treated as the standard PSS/E shape;
   7 or fewer is treated as the abbreviated shape observed in the load-only
   sample. Both shapes populate the same `ParsedLoad` dataclass.
4. Import-type detection (`FULL_TOPOLOGY_WITH_LOAD` vs `LOAD_ONLY`) is
   purely data-driven: zero parsed `TopologyBus` records means `LOAD_ONLY`,
   never a filename or user assertion (mirrors ADR-003's own "never by user
   assertion" principle for topology-reuse detection).
5. **Header metadata** (`frequency_hz`/`case_description`/`raw_created`,
   Phase 7 discovery-support enhancement) is extracted from the same
   case-identification header already read for `rev`/`sbase` — never a
   second pass over the file, and subject to the same best-effort,
   never-required rule as point 2: any field the header does not supply
   (or a differently-worded RAW writer comment) is simply `None`, never a
   parse failure.
6. **`ParsedLoad.owner`** (Phase 7A) is PSS/E's own `OWNER` field, carried
   through faithfully as-is — a raw operational attribute, never
   interpreted, classified, or mapped to any engineering meaning by this
   parser (see EDR-007 §7.3's own caution against assuming what an Owner
   code represents). `None` whenever the record uses the abbreviated
   7-field shape (point 3), which has no `OWNER` field at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.modules.psse_integration.bus_classification import BusClassification, classify_bus_name

_TERMINATOR_RE = re.compile(r"^\s*0\s*/\s*END OF\s+.+?(?:,\s*BEGIN\s+(.+?))?\s*$", re.IGNORECASE)
_EOF_MARKER = "Q"

# Sections this parser actually understands and extracts data from. Any
# other `current_section` value (including ones never seen in either sample
# file) is tolerated — its data lines are counted and skipped, never fatal.
_BUS_SECTION = "BUS DATA"
_LOAD_SECTION = "LOAD DATA"
_GENERATOR_SECTION = "GENERATOR DATA"
_BRANCH_SECTION = "BRANCH DATA"
_TRANSFORMER_SECTION = "TRANSFORMER DATA"

# Standard PSS/E LOAD DATA has 17 fields (I,ID,STAT,AREA,ZONE,PL,QL,IP,IQ,
# YP,YQ,OWNER,SCALE,INTRPT,DGENP,DGENQ,DGENF). The abbreviated shape
# observed in the load-only sample has 7 (I,ID,STAT,AREA,ZONE,PL,QL, the
# last two often blank) — anything with more fields than the abbreviated
# shape but fewer than the standard one is treated as abbreviated too
# (tolerant of a partially-trimmed variant), since PL/QL are always the
# last two fields actually present in that shape.
_STANDARD_LOAD_FIELD_COUNT = 17
_ABBREVIATED_LOAD_FIELD_COUNT = 7


@dataclass
class ParsedBus:
    bus_number: int
    bus_name: str | None
    base_kv: float
    ide: int
    area: int | None
    zone: int | None
    owner: int | None
    # Voltage solution results — per-snapshot state (ADR-003), never
    # structural. Carried on this dataclass only because the RAW file
    # format itself does not physically separate them from the structural
    # bus fields on the same line; the service layer is what actually
    # routes these into `LoadSnapshotBusState`, never into `TopologyBus`
    # (see models.py's module docstring).
    voltage_mag: float | None = None
    voltage_angle: float | None = None

    @property
    def bus_classification(self) -> BusClassification:
        """EDR-007 §4 naming-pattern classification (Phase 7A) — a thin,
        read-only accessor delegating to `bus_classification.classify_bus_name`.
        Never stored as a parsed field: it is always derived from
        `bus_name`, never itself parsed from the RAW file."""
        return classify_bus_name(self.bus_name)

    @property
    def in_service(self) -> bool:
        """Phase 7C — the same `ide != 4` rule `service.py` already applies
        when persisting `LoadSnapshotBusState.in_service` (PSS/E bus type 4
        = isolated), exposed here as a read-only accessor so Preview (zero
        persistence) can show the same "Operational Status" fact a
        committed snapshot would, with no duplicated rule."""
        return self.ide != 4


@dataclass
class ParsedLoad:
    bus_number: int
    load_id: str
    status: bool
    p_mw: float
    q_mvar: float
    # PSS/E's own OWNER field (position 11 of the standard 17-field shape) —
    # an operational attribute carried faithfully from the RAW file, never
    # interpreted here. Best-effort: `None` whenever the record uses the
    # abbreviated 7-field shape (module docstring point 3), which has no
    # OWNER field at all.
    owner: int | None = None


@dataclass
class ParsedGenerator:
    bus_number: int
    gen_id: str
    p_gen: float
    q_gen: float
    p_max: float | None
    p_min: float | None
    q_max: float | None
    q_min: float | None
    status: bool


@dataclass
class ParsedBranch:
    from_bus: int
    to_bus: int
    ckt_id: str
    r: float
    x: float
    b: float
    rate_a: float | None
    rate_b: float | None
    rate_c: float | None
    status: bool


@dataclass
class ParsedTransformer:
    from_bus: int
    to_bus: int
    tertiary_bus: int | None
    ckt_id: str
    r: float
    x: float
    rate_a: float | None
    status: bool


@dataclass
class ParsedCase:
    """The full result of parsing one RAW file. `rev`/`sbase` are
    best-effort (may be `None` — see module docstring point 2).
    `frequency_hz`/`case_description`/`raw_created` are likewise
    best-effort header metadata (module docstring point 5) — display-only,
    never structural, never required."""

    rev: int | None = None
    sbase: float | None = None
    frequency_hz: float | None = None
    case_description: str | None = None
    raw_created: str | None = None
    buses: list[ParsedBus] = field(default_factory=list)
    loads: list[ParsedLoad] = field(default_factory=list)
    generators: list[ParsedGenerator] = field(default_factory=list)
    branches: list[ParsedBranch] = field(default_factory=list)
    transformers: list[ParsedTransformer] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_full_topology(self) -> bool:
        """Data-driven import-type detection (module docstring point 4)."""
        return len(self.buses) > 0


class RawParseError(Exception):
    """Raised for a genuinely unparseable file — malformed enough that no
    meaningful data could be extracted at all."""


def _strip_comment(line: str) -> str:
    """Strips a trailing `/ comment` — respecting single-quoted strings, so
    a `/` inside a quoted name (unlikely, but not impossible) is not
    mistaken for a comment delimiter."""
    in_quote = False
    for i, ch in enumerate(line):
        if ch == "'":
            in_quote = not in_quote
        elif ch == "/" and not in_quote:
            return line[:i]
    return line


def _trailing_comment(line: str) -> str | None:
    """Returns the text after the first un-quoted `/` comment delimiter
    (mirrors `_strip_comment`'s own quote-awareness), or `None` if the line
    has no comment at all."""
    in_quote = False
    for i, ch in enumerate(line):
        if ch == "'":
            in_quote = not in_quote
        elif ch == "/" and not in_quote:
            return line[i + 1 :].strip()
    return None


# The RAW writer's own "created by" note (e.g. `PSS(R)E 34 RAW created by
# rawd34  WED, FEB 11 2026  14:43`) is free text produced by whichever tool
# wrote the file, not a formal RAW field — this pattern matches the one
# real writer tool observed in this project's own sample file
# (module docstring); a differently-worded comment from another tool
# simply yields `None` below, never a parse failure.
_RAW_CREATED_RE = re.compile(r"RAW created by\s+\S+\s+(.+)$", re.IGNORECASE)


def _extract_raw_created(comment: str | None) -> str | None:
    """Best-effort extraction of the RAW writer's own file-export note —
    this is the file's *export timestamp*, never the network study date
    (module docstring point 5). Returns `None` whenever the marker text
    isn't present; never raises."""
    if not comment:
        return None
    match = _RAW_CREATED_RE.search(comment)
    if not match:
        return None
    return re.sub(r"\s+", " ", match.group(1)).strip() or None


def _split_fields(line: str) -> list[str]:
    """Splits a data line on commas, respecting single-quoted strings, and
    strips surrounding whitespace/quotes from each field. A trailing
    comment (see `_strip_comment`) must already have been removed."""
    fields: list[str] = []
    current = []
    in_quote = False
    for ch in line:
        if ch == "'":
            in_quote = not in_quote
            continue
        if ch == "," and not in_quote:
            fields.append("".join(current).strip())
            current = []
            continue
        current.append(ch)
    fields.append("".join(current).strip())
    return fields


def _to_int(value: str, default: int | None = None) -> int | None:
    value = value.strip()
    if not value:
        return default
    try:
        return int(float(value))
    except ValueError:
        return default


def _to_float(value: str, default: float | None = None) -> float | None:
    value = value.strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


# A "no reading" load record (observed in the load-only sample as
# `I,'ID' / No Reading / <label>`) has a bus number and load id but no P/Q
# at all — a real, legitimate case (a meter simply did not report this
# cycle), not a malformed line. Fewer fields than this means there isn't
# even a load id, which genuinely is unparseable.
_MINIMUM_LOAD_FIELD_COUNT = 2


class _NoReading:
    """Sentinel distinguishing "valid record, no P/Q data this cycle" from
    "could not parse at all" — see `_parse_load_fields`."""


def _parse_load_fields(fields: list[str]) -> ParsedLoad | None | type[_NoReading]:
    if len(fields) < _MINIMUM_LOAD_FIELD_COUNT:
        return None
    bus_number = _to_int(fields[0])
    if bus_number is None:
        return None
    if len(fields) < _ABBREVIATED_LOAD_FIELD_COUNT:
        return _NoReading
    # Both the standard (17-field) and abbreviated (7-field) shapes agree
    # on field positions 0-6 (I, ID, STAT, AREA, ZONE, PL, QL) — see module
    # docstring point 3. OWNER (position 11) is only present in the
    # standard shape; the abbreviated shape simply has no such field.
    return ParsedLoad(
        bus_number=bus_number,
        load_id=fields[1] or "1",
        status=_to_int(fields[2], 1) == 1,
        p_mw=_to_float(fields[5], 0.0) or 0.0,
        q_mvar=_to_float(fields[6], 0.0) or 0.0,
        owner=_to_int(fields[11]) if len(fields) > 11 else None,
    )


def parse_raw(content: str) -> ParsedCase:
    """Parses PSS/E RAW file content (rev 34, per this phase's initial
    scope — see module docstring). Never raises for an unrecognized
    section; only raises `RawParseError` if the file is empty or the
    header line itself is unparseable garbage (not merely absent — an
    absent header, as in the load-only sample, is valid, see point 2)."""
    lines = content.splitlines()
    if not lines:
        raise RawParseError("The uploaded file is empty.")

    case = ParsedCase()
    current_section = "SYSTEM-WIDE DATA"
    # Position within the case-identification header (module docstring
    # point 5): line 1 is the numeric IC/SBASE/REV/.../BASFRQ line; lines 2
    # and 3 are the two fixed, free-text case-identification title lines
    # (always in this position when present — never detected by keyword);
    # anything beyond line 3 (GENERAL/GAUSS/RATING/... in newer RAW
    # revisions) is ignored, unchanged from before this enhancement.
    system_wide_data_line_index = 0
    case_title_line_1: str | None = None
    case_title_line_2: str | None = None
    unknown_sections_warned: set[str] = set()

    # Transformer records span multiple lines — tracked as an explicit
    # sub-state machine, since the number of remaining lines for the
    # current record depends on whether it is 2-winding or 3-winding
    # (module docstring point 1 applies here too: this must not assume a
    # fixed record length).
    transformer_lines_remaining = 0
    transformer_is_three_winding = False
    pending_transformer: ParsedTransformer | None = None

    for raw_line in lines:
        stripped = raw_line.rstrip("\r\n")
        if stripped.strip().upper() == _EOF_MARKER:
            break
        if not stripped.strip():
            continue

        terminator_match = _TERMINATOR_RE.match(stripped)
        if terminator_match:
            next_section = terminator_match.group(1)
            current_section = next_section.strip().upper() if next_section else "EOF"
            continue

        if stripped.lstrip().startswith("@!"):
            continue  # column-header comment line, never data

        # --- SYSTEM-WIDE DATA (case identification header) -------------
        if current_section == "SYSTEM-WIDE DATA":
            system_wide_data_line_index += 1
            if system_wide_data_line_index == 1:
                header_fields = _split_fields(_strip_comment(stripped))
                if len(header_fields) >= 3:
                    case.sbase = _to_float(header_fields[1])
                    case.rev = _to_int(header_fields[2])
                if len(header_fields) >= 6:
                    case.frequency_hz = _to_float(header_fields[5])
                case.raw_created = _extract_raw_created(_trailing_comment(stripped))
            elif system_wide_data_line_index == 2:
                # Case-identification title line 1 — free text, preserved
                # verbatim (never comment-stripped: unlike a data line, a
                # title line has no CSV structure of its own, so a `/`
                # within it is just text, not a comment delimiter).
                case_title_line_1 = stripped.strip() or None
            elif system_wide_data_line_index == 3:
                case_title_line_2 = stripped.strip() or None
            continue  # GENERAL / GAUSS / RATING etc. (rev 33+, line 4+) — ignored

        data = _strip_comment(stripped)
        if not data.strip():
            continue
        fields = _split_fields(data)

        if current_section == _BUS_SECTION:
            bus_number = _to_int(fields[0])
            if bus_number is None:
                continue
            base_kv = _to_float(fields[2], 0.0) or 0.0
            bus = ParsedBus(
                bus_number=bus_number,
                bus_name=fields[1] or None,
                base_kv=base_kv,
                ide=_to_int(fields[3], 1) or 1,
                area=_to_int(fields[4]),
                zone=_to_int(fields[5]),
                owner=_to_int(fields[6]),
                voltage_mag=_to_float(fields[7]) if len(fields) > 7 else None,
                voltage_angle=_to_float(fields[8]) if len(fields) > 8 else None,
            )
            case.buses.append(bus)

        elif current_section == _LOAD_SECTION:
            load = _parse_load_fields(fields)
            if load is _NoReading:
                case.warnings.append(f"No reading for load record (skipped): {stripped!r}")
            elif load is not None:
                case.loads.append(load)
            else:
                case.warnings.append(f"Could not parse LOAD DATA line: {stripped!r}")

        elif current_section == _GENERATOR_SECTION:
            bus_number = _to_int(fields[0])
            if bus_number is None:
                continue
            case.generators.append(
                ParsedGenerator(
                    bus_number=bus_number,
                    gen_id=fields[1] or "1",
                    p_gen=_to_float(fields[2], 0.0) or 0.0,
                    q_gen=_to_float(fields[3], 0.0) or 0.0,
                    q_max=_to_float(fields[4]) if len(fields) > 4 else None,
                    q_min=_to_float(fields[5]) if len(fields) > 5 else None,
                    p_max=_to_float(fields[16]) if len(fields) > 16 else None,
                    p_min=_to_float(fields[17]) if len(fields) > 17 else None,
                    status=_to_int(fields[14], 1) == 1 if len(fields) > 14 else True,
                )
            )

        elif current_section == _BRANCH_SECTION:
            from_bus = _to_int(fields[0])
            to_bus = _to_int(fields[1])
            if from_bus is None or to_bus is None:
                continue
            case.branches.append(
                ParsedBranch(
                    from_bus=from_bus,
                    to_bus=to_bus,
                    ckt_id=fields[2] or "1",
                    r=_to_float(fields[3], 0.0) or 0.0,
                    x=_to_float(fields[4], 0.0) or 0.0,
                    b=_to_float(fields[5], 0.0) or 0.0,
                    rate_a=_to_float(fields[7]) if len(fields) > 7 else None,
                    rate_b=_to_float(fields[8]) if len(fields) > 8 else None,
                    rate_c=_to_float(fields[9]) if len(fields) > 9 else None,
                    status=_to_int(fields[24], 1) == 1 if len(fields) > 24 else True,
                )
            )

        elif current_section == _TRANSFORMER_SECTION:
            if transformer_lines_remaining == 0:
                # This is line 1 of a new transformer record.
                from_bus = _to_int(fields[0])
                to_bus = _to_int(fields[1])
                tertiary_bus = _to_int(fields[2]) if len(fields) > 2 else None
                if tertiary_bus == 0:
                    tertiary_bus = None
                if from_bus is None or to_bus is None:
                    continue
                transformer_is_three_winding = tertiary_bus is not None
                pending_transformer = ParsedTransformer(
                    from_bus=from_bus,
                    to_bus=to_bus,
                    tertiary_bus=tertiary_bus,
                    ckt_id=fields[3] if len(fields) > 3 else "1",
                    r=0.0,
                    x=0.0,
                    rate_a=None,
                    status=_to_int(fields[11], 1) == 1 if len(fields) > 11 else True,
                )
                # 2-winding: 3 more lines (impedance, winding1, winding2).
                # 3-winding: 4 more lines (impedance, winding1, winding2, winding3).
                transformer_lines_remaining = 4 if transformer_is_three_winding else 3
            elif (
                transformer_lines_remaining in (4, 3)
                and pending_transformer is not None
                and (
                    (transformer_is_three_winding and transformer_lines_remaining == 4)
                    or (not transformer_is_three_winding and transformer_lines_remaining == 3)
                )
            ):
                # Impedance line — first two fields (R1-2, X1-2) are in the
                # same position for both 2- and 3-winding records.
                pending_transformer.r = _to_float(fields[0], 0.0) or 0.0
                pending_transformer.x = _to_float(fields[1], 0.0) or 0.0
                transformer_lines_remaining -= 1
            elif transformer_lines_remaining == 2 and pending_transformer is not None:
                # Winding 1 line — first rating (RATE1-1) at index 3.
                pending_transformer.rate_a = _to_float(fields[3]) if len(fields) > 3 else None
                transformer_lines_remaining -= 1
            else:
                # Winding 2 (and, for 3-winding, winding 3) — nothing else
                # captured at this phase's scope; just consume the line to
                # stay in sync with the file.
                transformer_lines_remaining -= 1
                if transformer_lines_remaining == 0 and pending_transformer is not None:
                    case.transformers.append(pending_transformer)
                    pending_transformer = None

        else:
            if current_section not in unknown_sections_warned:
                unknown_sections_warned.add(current_section)
                case.warnings.append(
                    f"Section '{current_section}' is not recognized by this parser — its "
                    "data (if any) was skipped."
                )

    # Title line 2 is conventionally the specific case/study identifier
    # (e.g. "CPF_03 JAN 2025"); title line 1 is typically a general study
    # description (e.g. "OPERATION STUDY") — preferred only when line 2 is
    # absent or blank, never both concatenated (module docstring point 5).
    case.case_description = case_title_line_2 or case_title_line_1

    return case
