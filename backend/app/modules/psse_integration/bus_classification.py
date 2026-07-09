"""Operational Bus classification (EDR-007 §4; Phase 7A implementation of
`docs/architecture/phase-7-operational-snapshot-correlation-implementation
-spec.md` §6).

A pure function over a bus name — no ORM objects, no I/O, no database
lookup — mirroring `signature.py` and `matching.py`'s own shape. This is
purely a **naming-pattern** classification: it decides which of EDR-007's
five Bus Name categories a name's shape matches. It makes no Engineering
Registry correlation decision (that remains `service.py`'s
`_match_substation_for_bus`, unchanged by this module) — a bus classified
`SWITCHYARD_BUS` here may still fail to correlate to any real Substation
Registry record; classification and correlation are deliberately separate
questions (EDR-007 §4.7 Correlation Philosophy).

Classification order is significant: the well-formed Switchyard/Split
Switchyard patterns are checked before the Fictitious-Bus heuristic, so a
mnemonic that happens to contain the substring "FIC" (e.g. a hypothetical
`XFIC132`) is still recognized as a Switchyard Bus, not misclassified as
Fictitious — the positive, well-defined pattern takes precedence over the
looser substring heuristic.
"""

from __future__ import annotations

import re
from typing import Literal

BusClassification = Literal[
    "SWITCHYARD_BUS",
    "SPLIT_SWITCHYARD_BUS",
    "FICTITIOUS_BUS",
    "BLANK_NAMED_BUS",
    "OTHER_NON_CONFORMING_BUS",
]

# EDR-007 §4.4/§4.5 naming conventions: <4-character mnemonic><nominal
# voltage>[<suffix>]. Voltage is 2-3 digits (e.g. 33, 132, 275, 500).
_SWITCHYARD_BUS_RE = re.compile(r"^[A-Za-z]{4}\d{2,3}$")
_SPLIT_SWITCHYARD_BUS_RE = re.compile(r"^[A-Za-z]{4}\d{2,3}[A-Za-z]$")

# Explicit Fictitious Bus naming patterns identified during the EDR-007
# discovery against the real sample RAW file (docs/samples/psse/
# 110226n.raw): the RAW author's own "FIC" tag (SDAOFIC, LMTMFIC, ATWRFIC,
# BPHEFIC1/2, SRYAFIC1/2), and the EDR-007 worked example anchor
# (TJGSM1A/TJGSM1B) — a generator-terminal pair that does not itself carry
# a "FIC" tag but was confirmed Fictitious by the Bus/Branch/Transformer
# Data discovery (EDR-007 §4.6). This is a deliberately narrow, evidence-
# based list, not a general heuristic — see EDR-007 §10 Open Questions for
# the acknowledged gap that further Fictitious Bus naming conventions may
# exist and are not yet identified.
_FICTITIOUS_BUS_ANCHOR_NAMES = {"TJGSM1A", "TJGSM1B"}


def classify_bus_name(bus_name: str | None) -> BusClassification:
    """Classifies a Bus Name into one of EDR-007 §4's five categories.
    Deterministic and total — every possible `bus_name` value (including
    `None` or whitespace-only) maps to exactly one classification, never
    raises."""
    if bus_name is None or not bus_name.strip():
        return "BLANK_NAMED_BUS"

    name = bus_name.strip()

    if _SPLIT_SWITCHYARD_BUS_RE.match(name):
        return "SPLIT_SWITCHYARD_BUS"
    if _SWITCHYARD_BUS_RE.match(name):
        return "SWITCHYARD_BUS"
    if "FIC" in name.upper() or name.upper() in _FICTITIOUS_BUS_ANCHOR_NAMES:
        return "FICTITIOUS_BUS"
    return "OTHER_NON_CONFORMING_BUS"
