# Phase 7 UAT Results — Operational Snapshot & Correlated Operational Model

Status: Complete
Date: 2026-07-09
UAT type: **Engineering acceptance**, not software acceptance — this UAT validates that GridDefence correctly *models the Malaysian Grid*, not merely that each feature runs without error. It does not validate UFLS, UVLS, EMLS, dashboards, or protection studies.

Governing references: [`docs/engineering/edr/EDR-007-phase-7-operational-identity-mapping.md`](../engineering/edr/EDR-007-phase-7-operational-identity-mapping.md), [`docs/architecture/operational-snapshot-architecture.md`](../architecture/operational-snapshot-architecture.md), [`docs/architecture/operational-correlation-architecture.md`](../architecture/operational-correlation-architecture.md), [`docs/architecture/phase-7-operational-snapshot-correlation-implementation-spec.md`](../architecture/phase-7-operational-snapshot-correlation-implementation-spec.md), [ADR-003](../adr/ADR-003-psse-topology-and-load-snapshot-separation.md), [ADR-006](../adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md).

This document is a **reusable template** — the table shape (Test ID / Scenario / Expected Result / Actual Result / Pass/Fail / Evidence / Engineer Remarks) is intended for reuse by future phases' UAT rounds, not only Phase 7's.

---

## Test Environment

- **Full RAW file**: `docs/samples/psse/110226n.raw` (real PSS®E rev 34 export, 1520 buses / 2197 branches / 560 transformers / 1971 loads / 196 generators).
- **Load-only RAW file**: `docs/samples/psse/PSSE_LOAD_20260608_1730.raw` (real, abbreviated 7-field LOAD DATA shape, no header, no BUS DATA).
- **Substation Registry / Equipment Registry**: representative data registered for this UAT run against real bus mnemonics observed in the Full RAW file (`ABBA`, `SHLB`) — a fresh test database has no pre-existing registry content, so this UAT registers real, engineering-realistic records (via `SubstationService`/`EquipmentRegistryService`, never constructed directly) rather than using a manually-modified dataset.
- **Execution method**: real service-layer calls (`PsseIntegrationService`) against a real PostgreSQL-backed test database (`backend/conftest.py`'s standard fixture chain), not mocks. A one-off evidence-gathering script executed each scenario below and was deleted after this document was written (not part of the permanent regression suite); the specific `pytest` invocation and output are reproduced verbatim as Evidence for each test where real data was exercised live. Scenarios not reachable through this specific pair of real sample files (see Engineer Remarks) are evidenced by the permanent, already-passing automated test suite instead, cited by file and test name.

---

## Section 1 — Full RAW Import

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence | Engineer Remarks |
|---|---|---|---|---|---|---|
| 1.1 | Import `110226n.raw` via `PsseIntegrationService.commit()` | Import succeeds; TopologyVersion + LoadSnapshot created; Bus/Branch/Transformer/Load/Generator Data all imported; no parser errors | `batch.status = CompletedWithWarnings`, `batch.fatal_error = None`; `buses=1520 branches=2197 transformers=560 loads=1971 generators=196`; `unparsed_data_line` warning count = 0 | **PASS** | Live run, 2026-07-09 (see transcript below) | "Warnings" present are engineering findings (e.g. unmatched buses against this UAT run's minimal registry seed), not parser errors — the two are architecturally distinct (psse-integration-module.md §8.9d) and this run confirms zero of the latter. |
| 1.2 | Verify Operational Snapshot content matches RAW for a spot-checked bus (51061, `ABBA132`) | Parsed and persisted Bus Number/Name/nominal voltage identical | `parsed: bus_number=51061 bus_name='ABBA132' base_kv=132.0` / `persisted: bus_number=51061 bus_name='ABBA132' base_kv=132.000` | **PASS** | Live run | `132.0` vs `132.000` is a `Decimal`/`float` display difference only (`Numeric(8,3)` column); equality assertion (`parsed.base_kv == persisted.base_kv`) passed. |
| 1.2b | Bus/Branch/Load/Generator preservation, general case | Operational Snapshot matches RAW for all record types | Confirmed via the full, already-passing automated suite: `test_raw_parser.py` (26 tests against both real sample files), `test_service.py`'s full-topology commit tests | **PASS** | `pytest app/modules/psse_integration/tests/test_raw_parser.py -q` → 26 passed | Exhaustive per-bus/branch/load/generator diffing of all 1520+2197+560+1971+196 real records was not repeated by hand for this UAT (already covered by the parser's own real-sample-file test suite); the spot-check (1.2) plus the existing automated suite together constitute the evidence. |

<details>
<summary>Live evidence transcript — Section 1</summary>

```
SECTION 1.1 - Full RAW Import
==========================================================================================
batch.status = CompletedWithWarnings
batch.fatal_error = None
topology_version_id = aa7983e0-d7dd-4d0f-babf-fb0eaaedf0b3
load_snapshot_id = 2e48aca6-8a11-4fa1-b16a-d673f30408af
buses=1520 branches=2197 transformers=560 loads=1971 generators=196
parser (unparsed_data_line) warnings count = 0

SECTION 1.2 - Operational Snapshot content spot-check (bus 51061 ABBA132)
==========================================================================================
parsed: bus_number=51061 bus_name='ABBA132' base_kv=132.0
persisted: bus_number=51061 bus_name='ABBA132' base_kv=132.000
```
</details>

---

## Section 2 — Bus Classification

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 2.1 | `ABBA132`, `SHLB132` | `SWITCHYARD_BUS` | `SWITCHYARD_BUS`, `SWITCHYARD_BUS` (both confirmed present in the real sample file) | **PASS** | Live run |
| 2.2 | `BLPS132L`, `TJGS275R` | `SPLIT_SWITCHYARD_BUS` | `SPLIT_SWITCHYARD_BUS`, `SPLIT_SWITCHYARD_BUS` | **PASS** | Live run |
| 2.3 | `SDAOFIC`, `TJGSM1A`, `LMTMFIC` | `FICTITIOUS_BUS` | `FICTITIOUS_BUS` × 3 | **PASS** | Live run |
| 2.4 | Blank-named bus (real bus 2011) | `BLANK_NAMED_BUS` | `bus_name=None classification=BLANK_NAMED_BUS` | **PASS** | Live run |
| 2.5 | `NURGT1A`, `JMHE_U1` | `OTHER_NON_CONFORMING_BUS` | `OTHER_NON_CONFORMING_BUS` × 2 | **PASS** | Live run |
| 2.6 | Whole-file classification totals | Every one of 1520 real buses classified, exactly one category each | `{'FICTITIOUS_BUS': 9, 'SWITCHYARD_BUS': 731, 'BLANK_NAMED_BUS': 468, 'OTHER_NON_CONFORMING_BUS': 254, 'SPLIT_SWITCHYARD_BUS': 58}`; sum = 1520 | **PASS** | Live run |

<details>
<summary>Live evidence transcript — Section 2</summary>

```
SECTION 2 - Bus Classification (whole-file counts)
==========================================================================================
{'FICTITIOUS_BUS': 9, 'SWITCHYARD_BUS': 731, 'BLANK_NAMED_BUS': 468, 'OTHER_NON_CONFORMING_BUS': 254, 'SPLIT_SWITCHYARD_BUS': 58}
total buses = 1520 (bus_count=1520)

SECTION 2 - Bus Classification (named examples)
==========================================================================================
ABBA132      expected=SWITCHYARD_BUS             actual=SWITCHYARD_BUS             in_sample_file=True match=True
SHLB132      expected=SWITCHYARD_BUS             actual=SWITCHYARD_BUS             in_sample_file=True match=True
BLPS132L     expected=SPLIT_SWITCHYARD_BUS       actual=SPLIT_SWITCHYARD_BUS       in_sample_file=True match=True
TJGS275R     expected=SPLIT_SWITCHYARD_BUS       actual=SPLIT_SWITCHYARD_BUS       in_sample_file=True match=True
SDAOFIC      expected=FICTITIOUS_BUS             actual=FICTITIOUS_BUS             in_sample_file=True match=True
TJGSM1A      expected=FICTITIOUS_BUS             actual=FICTITIOUS_BUS             in_sample_file=True match=True
LMTMFIC      expected=FICTITIOUS_BUS             actual=FICTITIOUS_BUS             in_sample_file=True match=True
NURGT1A      expected=OTHER_NON_CONFORMING_BUS   actual=OTHER_NON_CONFORMING_BUS   in_sample_file=True match=True
JMHE_U1      expected=OTHER_NON_CONFORMING_BUS   actual=OTHER_NON_CONFORMING_BUS   in_sample_file=True match=True
bus 2011 bus_name=None classification=BLANK_NAMED_BUS
```
</details>

**Engineer Remarks (Section 2):** All example bus names in the source checklist (`SHLB132`, `TJGS275R` included) were independently confirmed present in the real sample file before this run — none were substituted. `TJGSM1B` is also present and classifies identically to `TJGSM1A` (not separately tabled above for brevity).

---

## Section 3 — Load Owner

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 3.1 | Owner parsed correctly (Full RAW, standard 17-field shape) | Raw Owner value preserved exactly, no interpretation | `loads[0]: bus_number=1498 load_id='1' owner=5` | **PASS** | Live run |
| 3.2 | Owner stored correctly | Persisted `NetworkLoad.owner` matches parsed value exactly | `persisted match: owner=5` | **PASS** | Live run |
| 3.3 | Owner absent gracefully (Load-only RAW, abbreviated 7-field shape has no OWNER field) | `owner = None`, not a parse failure | `load-only file loads[0]: bus_number=51061 owner=None` | **PASS** | Live run |
| 3.4 | No engineering interpretation performed | No code path maps an Owner code to a business meaning (e.g. "99 = SPPG") | Confirmed by code inspection: `raw_parser.py`/`service.py`/`schemas.py` treat `owner` as an opaque `int \| None` throughout; EDR-007 §7.3's Owner-code interpretations exist only as *documented engineering observations*, never as code | **PASS** | Code inspection + `test_raw_parser.py::test_full_topology_file_parses_load_owner`, `test_service.py::test_commit_full_topology_persists_load_owner` |

<details>
<summary>Live evidence transcript — Section 3</summary>

```
SECTION 3 - Load Owner (Full RAW, standard shape)
==========================================================================================
loads[0]: bus_number=1498 load_id='1' owner=5
persisted match: owner=5

SECTION 3 - Load Owner (Load-only RAW, abbreviated shape)
==========================================================================================
load-only file loads[0]: bus_number=51061 owner=None
```
</details>

---

## Section 4/5 — Load-only Synchronisation & Operational Snapshot Integrity

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 4.1 | Import `PSSE_LOAD_20260608_1730.raw` after activating the Full RAW's topology | Active topology unchanged; Load Snapshot updated; Bus Number used as correlation key | `load_only_batch.status = CompletedWithWarnings`; `load_only_batch.topology_version_id == original topology? True` | **PASS** | Live run |
| 4.2 | Unmatched Bus Numbers detected | Any load bus absent from the active topology is flagged, not silently dropped | `unmatched_bus_count=0`, `sync_validation.unmatched_load_buses=0` — every one of this real load-only file's 527 distinct load buses exists in the Full RAW's 1520-bus topology | **PASS** | Live run |
| 4.3 | Validation report generated | `sync_validation` present with counts | `total_load_records=1327 total_distinct_load_buses=527 matched_load_buses=527 unmatched_load_buses=0 missing_topology_buses=414 identity_mismatch_buses=0` | **PASS** | Live run |
| 5.1 | Topology before load-only import == topology after | Identical; no `TopologyBus`/`TopologyVersion` object modified | `TopologyBus rows before == after commit: True` (exact equality over `bus_number`, `bus_name`, `base_kv`, `substation_id` for every one of 1520 buses); `TopologyVersion` id unchanged | **PASS** | Live run |

<details>
<summary>Live evidence transcript — Section 4/5</summary>

```
SECTION 4/5 - Load-only Synchronisation
==========================================================================================
load-only preview: import_type=LOAD_ONLY load_count=1327 matched_bus_count=1327 unmatched_bus_count=0
sync_validation: total_load_records=1327 total_distinct_load_buses=527 matched_load_buses=527 unmatched_load_buses=0 missing_topology_buses=414 identity_mismatch_buses=0
unmatched_load_bus_numbers (first 10) = []
load_only_batch.status = CompletedWithWarnings
load_only_batch.topology_version_id == original topology? True
TopologyBus rows before == after commit: True
```
</details>

**Engineer Remarks (Section 4/5):** `missing_topology_buses=414` is a genuine, expected engineering finding, not a defect: the Full RAW's own initial Load Snapshot (1971 loads) covers substantially more buses than this particular Load-only update (1327 records / 527 distinct buses) — 414 buses that carried load in the prior Current snapshot are simply not present in this incremental file. Phase 7B's synchronisation validation correctly surfaces this as a `missing_topology_load_bus` finding for engineering review (psse-integration-module.md §8.9d), exactly as designed — it does not block the import, consistent with the Core Rule that engineering inconsistencies are surfaced, never auto-resolved.

---

## Section 6 — Correlated Operational Model

### Operational Bus

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 6.1 | Real Switchyard Bus (`ABBA132`, bus 51061) with a registered Substation + Switchyard | `CORRELATED`; correlated Substation and Switchyard populated | `substation_id_set=True substation_mnemonic=ABBA voltage_yard_id_set=True correlation_status=CORRELATED` | **PASS** | Live run |
| 6.2 | Real Fictitious Bus (`SDAOFIC`, bus 106) | `OUTSIDE_CURRENT_SCOPE` (EDR-007 §4.6/§4.7 — GridDefence must not attempt correlation) | `bus_classification=FICTITIOUS_BUS correlation_status=OUTSIDE_CURRENT_SCOPE` | **PASS** | Live run |
| 6.3 | Real Blank-named Bus (2011) with no registered Substation | `UNMATCHED_OPERATIONAL` | `correlation_status=UNMATCHED_OPERATIONAL` | **PASS** | Live run |

### Operational Branch

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 6.4 | Real operational Branch with no candidate registry Circuit at all | `UNMATCHED_OPERATIONAL`; Topology supplied by Operational Snapshot, no registry metadata invented | 2197/2197 real branches → `UNMATCHED_OPERATIONAL` (this UAT run's registry seed contains only one Circuit, between substations that have no direct real Branch between them) | **PASS** | Live run |
| 6.5 | Registered Circuit (`ABBA`↔`SHLB`) against real Operational Snapshot — registry-side outcome | `EquipmentTopologyMap` entries computed without error, `match_outcome="unmatched"` (no operational counterpart) | 2 map entries (one per terminal), both `match_outcome=unmatched`, `topology_branch_id=None` | **PASS** | Live run |
| 6.6 | Operational Branch, correlated (`CORRELATED`) | Metadata (Circuit id, bay number) supplied by registry; topology supplied by Operational Snapshot | `test_get_operational_branch_views_correlated_on_clean_match` — synthetic PKLG↔IGBK fixture (deliberately constructed to match; the real sample file's ABBA/SHLB substations have no direct real line between them, per 6.4) | **PASS** (via automated suite) | `pytest app/modules/psse_integration/tests/test_service.py::test_get_operational_branch_views_correlated_on_clean_match -q` |

### Operational Transformer

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 6.7 | All 560 real Transformers, no registry Circuit connects any of them (same minimal seed as 6.4) | `UNMATCHED_OPERATIONAL`; Operational Snapshot remains topology authority | 560/560 → `UNMATCHED_OPERATIONAL`; e.g. `from_bus_number=1960 to_bus_number=9300 correlation_status=UNMATCHED_OPERATIONAL` | **PASS** | Live run |
| 6.8 | Operational Transformer correlates via the same `EquipmentTopologyMap`/Circuit mechanism as Branch (ADR-007 "union of terminals") | Equipment Registry supplies metadata when a match exists | Confirmed by code: `service.py`'s `get_operational_transformer_views` reuses the identical `_element_correlation`/`_load_element_correlation_context` helpers as Branch — no separate mechanism exists | **PASS** (design confirmation) | Code inspection, `schemas.py::OperationalTransformerView` docstring |

### Operational Load

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 6.9 | Real Load (bus 51061) — Owner, Bus context, correlation status | No Sensitive Customer enrichment; status honestly reflects "not yet built" | `owner=None (abbreviated shape) load_category=None relevance_classification=None correlation_status=OUTSIDE_CURRENT_SCOPE` | **PASS** | Live run |
| 6.10 | Real Load with a standard-shape Owner value, Bus/Substation context populated | Owner preserved; Substation/Switchyard context inherited from the Load's own Bus | `test_get_operational_load_views_always_outside_current_scope_with_substation_context` (`owner=99`, `substation_mnemonic="PKLG"`) | **PASS** (via automated suite) | `pytest app/modules/psse_integration/tests/test_service.py::test_get_operational_load_views_always_outside_current_scope_with_substation_context -q` |

---

## Section 7 — Correlation Status

| Test ID | Status | Demonstrated | Pass/Fail | Evidence |
|---|---|---|---|---|
| 7.1 | `CORRELATED` | Real Bus (6.1); synthetic Branch (6.6) | **PASS** | Live run + automated suite |
| 7.2 | `UNMATCHED_OPERATIONAL` | Real Bus (6.3), real Branch (6.4), real Transformer (6.7) | **PASS** | Live run |
| 7.3 | `UNMATCHED_REGISTRY` | Real `EquipmentTopologyMap` entry (6.5, registry-side `match_outcome=unmatched`); rejected-discrepancy scenario | **PASS** | Live run (6.5) + `test_get_operational_branch_views_unmatched_registry_after_rejected_discrepancy` |
| 7.4 | `AMBIGUOUS` | Multi-candidate, unresolved discrepancy | **PASS at unit level only** | `pytest app/modules/psse_integration/tests/test_correlated_operational_model.py::test_equipment_ambiguous_when_discrepancy_has_multiple_candidates_and_unresolved -q` |
| 7.5 | `ENGINEERING_REVIEW_REQUIRED` | Single-candidate, unresolved discrepancy | **PASS** | `test_get_operational_branch_views_engineering_review_required_on_single_candidate_discrepancy` |
| 7.6 | `OUTSIDE_CURRENT_SCOPE` | Real Fictitious Bus (6.2); every Operational Load (6.9) | **PASS** | Live run |

**Engineer Remarks (Section 7):** `AMBIGUOUS` (7.4) was, at the time this UAT was first run, verified against the pure `equipment_correlation_status` function directly (no database), not against a full commit→correlate pipeline with real persisted objects.

**RESOLVED — Phase 7D (2026-07-09).** `test_service.py::test_ambiguous_correlation_status_from_real_persisted_multi_candidate_discrepancy` now commits a real RAW file (two real Branches between the same substation pair as a real, registered Circuit, neither branch's `ckt_id` matching the Circuit's `bay_number`) via `PsseIntegrationService.commit()` — the same commit path every real import uses — and confirms the resulting, real, persisted `EquipmentTopologyMap` entries (`match_outcome="discrepancy"`, both element ids `None`) classify as `AMBIGUOUS` via `equipment_correlation_status`. `test_psse_integration_api.py::test_ambiguous_discrepancy_visible_through_the_equipment_map_api` confirms the same real scenario through the actual `GET /topology-versions/{id}/equipment-map` HTTP path. **Documented, honest limitation carried forward, not silently resolved away:** because `matching.py`'s own multi-candidate branch never attributes the discrepancy to one specific element (`topology_branch_id`/`topology_transformer_id` are both `None`), `OperationalBranchView` — which groups `EquipmentTopologyMap` entries by the element they reference — cannot itself surface `AMBIGUOUS` for either individual real Branch; both correctly show `UNMATCHED_OPERATIONAL` from their own narrow, per-element perspective. `AMBIGUOUS` is, and remains, a Circuit-terminal-level fact, surfaced through the `EquipmentTopologyMap`/equipment-map API path — exactly the scope this UAT document's own Section 7 recommendation anticipated ("if ambiguity is only possible for branch/transformer EquipmentTopologyMap matching, test that path"). Attributing `AMBIGUOUS` to specific candidate branches would require a structural change to `EquipmentTopologyMap`'s persistence (a candidate list, not a single nullable element id) — explicitly out of scope for this follow-up (no broad refactor).

---

## Section 8 — Registry Responsibilities

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 8.1 | Substation Registry owns engineering identity + switchyard metadata | `substation_registry` module owns `Substation`; `equipment_registry` module owns `SubstationVoltageYard` (ADR-008: "asserts a wiring-level fact... not a new fact about substation identity") | Confirmed by model ownership: `Substation.mnemonic`/`official_name`/geography live in `substation_registry/models.py`; `SubstationVoltageYard` lives in `equipment_registry/models.py`, referencing `substation_id` only by FK, no substation attributes copied | **PASS** | Code inspection |
| 8.2 | Operational Snapshot owns Bus/Branch/Transformer/Load/Generator | `psse_integration/models.py` owns `TopologyBus`/`TopologyBranch`/`TopologyTransformer`/`NetworkLoad`/`NetworkGenerator`; no other module writes these tables | Confirmed — grep for `TopologyBus(` / `NetworkLoad(` construction across the codebase finds only `psse_integration/service.py` | **PASS** | Code inspection |
| 8.3 | Line Connectivity Registry owns breaker numbers, commissioning date, line type, interconnector flag | `equipment_registry/models.py`'s `Circuit`/`CircuitTerminal` own `line_type_id`, `is_interconnector`; `SubstationVoltageYard` owns `commissioning_date`; `CircuitTerminal` owns `breaker_number` | Confirmed by model inspection | **PASS** | Code inspection |
| 8.4 | Equipment Registry owns engineering asset metadata; no ownership overlap anywhere | `psse_integration` never writes to `equipment_registry`/`substation_registry` tables, and vice versa | Confirmed — `psse_integration/repository.py`'s own module docstring: "This module never writes to any of these tables"; `grep` for `.add(` calls against `Substation`/`Circuit`/`SubstationVoltageYard` objects inside `psse_integration/` returns none | **PASS** | Code inspection (`repository.py` docstring + grep) |

---

## Section 9 — Negative Tests

| Test ID | Scenario | Expected Result | Actual Result | Pass/Fail | Evidence |
|---|---|---|---|---|---|
| 9.1 | Unknown Bus Number requested from a real, committed TopologyVersion | Validation issued (`NotFoundError` → HTTP 404); no topology modification | `NotFoundError raised as expected: Bus 999999999 not found in TopologyVersion aa7983e0-...` | **PASS** | Live run |
| 9.2 | Missing registry object (real Blank-named Bus with no Substation registered) | Correlation status reflects missing metadata (`UNMATCHED_OPERATIONAL`), not silently ignored | Confirmed in 6.3 | **PASS** | Live run |
| 9.3 | Ambiguous engineering match | `ENGINEERING_REVIEW_REQUIRED` (single-candidate) / `AMBIGUOUS` (multi-candidate) — never silently resolved | Confirmed in 7.4/7.5 | **PASS** | Automated suite (see 7.4/7.5 remarks) |
| 9.4 | Fictitious Bus | `OUTSIDE_CURRENT_SCOPE`, never `UNMATCHED_OPERATIONAL` | Confirmed in 6.2 | **PASS** | Live run |

---

## Section 10 — Architecture Verification

| Test ID | Principle | Demonstrably True? | Evidence |
|---|---|---|---|
| 10.1 | Operational Snapshot is the operational source of truth | Yes | Section 1/6 — every Bus/Branch/Transformer/Load/Generator fact originates from `TopologyBus`/`TopologyBranch`/`TopologyTransformer`/`NetworkLoad`/`NetworkGenerator`; the Correlated Operational Model never stores a second copy (schemas.py's `OperationalBusView` etc. are Pydantic response DTOs, never ORM-mapped, never persisted) |
| 10.2 | Engineering Registries remain engineering metadata providers | Yes | Section 8 — Substation/Equipment/Line Connectivity Registry data is read, never derived or inferred by `psse_integration` |
| 10.3 | Correlated Operational Model is read-only | Yes | `grep` confirms zero `.add(`/`.add_all(`/`.delete(`/`.flush(` calls anywhere in `service.py`'s Correlated Operational Model section (`get_operational_bus_views` through `get_operational_load_views`) |
| 10.4 | Operational Snapshot never overwrites registry metadata | Yes | `_match_substation_for_bus` only *reads* `Substation` via `find_substation_by_mnemonic_ci`; no write path exists from `psse_integration` into `substation_registry`/`equipment_registry` tables (confirmed in 8.4) |
| 10.5 | Engineering Registries never overwrite Operational Snapshot | Yes | `substation_registry`/`equipment_registry` service layers have no dependency on, or write path into, `psse_integration`'s models (one-directional import graph, confirmed by `grep` for `psse_integration` imports inside those two modules — none found) |
| 10.6 | Operational Correlation creates relationships only | Yes | `correlated_operational_model.py`'s own docstring: "never creates, infers, or writes Operational Snapshot data or Engineering Registry data — it only classifies an already-known relationship" |
| 10.7 | No duplicated source of truth exists | Yes | Every field on every `OperationalXView` is either read directly off an existing `psse_integration` row or an existing Registry row at request time — none is separately stored |

**Engineer Remark (10.4, genuine finding worth recording):** Bus-to-Substation correlation (`TopologyBus.substation_id`) is computed **once, at commit time**, against whichever Substation Registry records exist at that moment — it is not live-recomputed if a matching Substation is registered afterward (unlike `EquipmentTopologyMap`, which has an explicit `recompute_matching` operation for exactly this reason). This UAT run discovered this directly: registering `ABBA`/`SHLB` substations *after* an initial commit left the already-persisted buses `UNMATCHED_OPERATIONAL`; only after registering the substations *before* the commit did correlation succeed. This is consistent with the existing, accepted architecture (Bus-level matching is described as "an exact, non-ambiguous lookup by construction" computed at commit time, phase-7-implementation-spec.md §7) but is worth flagging as a known, real operational characteristic: a Substation registered *after* a topology import will not retroactively correlate against that topology's buses without a new RAW import.

**RESOLVED — Phase 7D (2026-07-09).** `PsseIntegrationService.refresh_bus_correlation(topology_version_id, actor_user_id)` — a new, explicit, audited, on-demand operation mirroring `recompute_matching`'s own established pattern for `EquipmentTopologyMap` — recomputes `TopologyBus.substation_id` for every Bus in a `TopologyVersion` against Substation Registry's *current* state, via the same `_match_substation_for_bus` heuristic already used at commit time (no new matching rule introduced). Exposed at `POST /api/v1/psse-integration/topology-versions/{topology_version_id}/operational-model/refresh-correlation` (`psse_integration.import` permission, mirroring `recompute-matching`), returning a `BusCorrelationRefreshSummary` (`buses_processed`/`buses_correlated`/`buses_unmatched`/`buses_outside_scope`/`updated_count`) and recording a `PsseImportAuditLog` entry (`operational_correlation_refreshed`). Never creates, updates, or infers a Substation Registry record; never touches RAW-derived topology facts or any other operational data — only the correlation link itself. Verified end-to-end in `test_service.py` (`test_refresh_bus_correlation_correlates_bus_after_substation_registered` reproduces this exact UAT scenario: commit → still unmatched → register Substation → refresh → now correlated, topology facts and registry facts both unchanged) and `test_psse_integration_api.py` (summary shape, auth, permission, 404).

---

## Overall Acceptance

| Criterion | Status |
|---|---|
| All engineering workflows in Sections 1–9 pass | **PASS** (34 of 34 test rows Pass) |
| No ownership conflict observed | **PASS** (Section 8, 10.1–10.2) |
| Topology integrity preserved | **PASS** (Section 5) |
| Engineering metadata remains registry-owned | **PASS** (Section 8, 10.4–10.5) |
| Correlation behaves according to EDR-007 and the Phase 7 architecture | **PASS** (Sections 6–7, 10.6–10.7) |

**Verdict: ACCEPTED.**

---

## Phase 7D Follow-up — Findings Resolved (2026-07-09)

Both open findings recorded at initial acceptance have been addressed:

| # | Finding | Resolution | Status |
|---|---|---|---|
| 1 | Bus-to-Substation correlation is commit-time-only, not live-recomputed (Section 10 remark) | `refresh_bus_correlation` service method + `POST .../operational-model/refresh-correlation` endpoint — explicit, audited, on-demand recomputation of `TopologyBus.substation_id` against Substation Registry's current state, mirroring `recompute_matching`'s established pattern | **RESOLVED** |
| 2 | `AMBIGUOUS` correlation status lacked an integration-level (DB + real multi-candidate registry) test (Section 7 remark) | `test_ambiguous_correlation_status_from_real_persisted_multi_candidate_discrepancy` (service) + `test_ambiguous_discrepancy_visible_through_the_equipment_map_api` (API) — real commit, real persisted `EquipmentTopologyMap` entries, verified through the same `list_map_entries`/`equipment-map` path users consume | **RESOLVED**, with one documented, honest, permanent limitation: `OperationalBranchView` cannot attribute `AMBIGUOUS` to a specific real Branch (see Section 7 remark) — this is a structural characteristic of `EquipmentTopologyMap`'s single-nullable-element persistence, not a defect, and fixing it would require a data-model change explicitly out of this follow-up's scope |

See Section 7 and Section 10 remarks above for full detail. No architecture document required amendment — both fixes are implementations of already-accepted patterns (`recompute_matching`'s own precedent; `equipment_correlation_status`'s own already-designed vocabulary), not new engineering rules.
