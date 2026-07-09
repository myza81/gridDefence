/**
 * Mirrors backend/app/modules/psse_integration/schemas.py. The frontend
 * performs no authoritative engineering logic (CLAUDE.md A12) — these types
 * exist only to describe the API contract the backend already enforces.
 */

import type { UserSummary } from "../iam/types";

export type ImportType = "FULL_TOPOLOGY_WITH_LOAD" | "LOAD_ONLY";
export type BatchStatus = "Parsing" | "Completed" | "CompletedWithWarnings" | "Failed";
export type VersionStatus = "Imported" | "Current" | "Superseded";
export type MatchOutcome = "clean_match" | "unmatched" | "discrepancy";
export type DiscrepancyResolution = "accepted" | "rejected";
export type JobRunStatus = "queued" | "started" | "finished" | "failed";

/** EDR-007 §4 Bus Name naming-pattern classification (Phase 7A) — a
 * read-only, derived-from-name accessor, never a registry correlation
 * decision. See `matched_bus_count`/`unmatched_bus_count` on
 * `PreviewResult` for the separate, existing correlation-status figures. */
export type BusClassification =
  | "SWITCHYARD_BUS"
  | "SPLIT_SWITCHYARD_BUS"
  | "FICTITIOUS_BUS"
  | "BLANK_NAMED_BUS"
  | "OTHER_NON_CONFORMING_BUS";

/** Unified Correlation Status vocabulary (Phase 7C, Correlated Operational
 * Model) — applies consistently across Bus/Branch/Transformer/Load views. */
export type CorrelationStatus =
  | "CORRELATED"
  | "UNMATCHED_OPERATIONAL"
  | "UNMATCHED_REGISTRY"
  | "AMBIGUOUS"
  | "OUTSIDE_CURRENT_SCOPE"
  | "ENGINEERING_REVIEW_REQUIRED";

/** One PSS/E bus record, exactly as the parser produced it — no
 * engineering translation, no registry correlation (Operational Context
 * Inspector). Mirrors backend `ParsedBusRow`/`raw_parser.ParsedBus`
 * field-for-field.
 *
 * `in_service`/`substation_id`/`substation_mnemonic`/`voltage_yard_id`/
 * `correlation_status` (Phase 7C) are Preview-time Correlated Operational
 * Model enrichment — `null` when not computed (e.g. a load-only case's
 * always-empty bus list). */
export interface ParsedBusRow {
  bus_number: number;
  bus_name: string | null;
  base_kv: number;
  ide: number;
  area: number | null;
  zone: number | null;
  owner: number | null;
  voltage_mag: number | null;
  voltage_angle: number | null;
  bus_classification: BusClassification;
  in_service: boolean | null;
  substation_id: string | null;
  substation_mnemonic: string | null;
  voltage_yard_id: string | null;
  correlation_status: CorrelationStatus | null;
}

export interface ParsedLoadRow {
  bus_number: number;
  load_id: string;
  status: boolean;
  p_mw: number;
  q_mvar: number;
  /** PSS/E's own raw Owner field (Phase 7A, EDR-007 §7.3) — carried
   * through faithfully, never interpreted or classified. */
  owner: number | null;
}

export interface ParsedGeneratorRow {
  bus_number: number;
  gen_id: string;
  p_gen: number;
  q_gen: number;
  p_max: number | null;
  p_min: number | null;
  q_max: number | null;
  q_min: number | null;
  status: boolean;
}

export interface ParsedBranchRow {
  from_bus: number;
  to_bus: number;
  ckt_id: string;
  r: number;
  x: number;
  b: number;
  rate_a: number | null;
  rate_b: number | null;
  rate_c: number | null;
  status: boolean;
}

export interface ParsedTransformerRow {
  from_bus: number;
  to_bus: number;
  tertiary_bus: number | null;
  ckt_id: string;
  r: number;
  x: number;
  rate_a: number | null;
  status: boolean;
}

export interface PreviewResult {
  import_type: ImportType;
  // Network-size fields (Phase 6 engineering presentation refinement) —
  // read directly off the parsed RAW case, never recomputed by the
  // frontend. `raw_version` is best-effort and may be `null`.
  raw_version: number | null;
  bus_count: number;
  branch_count: number;
  transformer_count: number;
  load_count: number;
  generator_count: number;
  computed_signature: string | null;
  topology_reused: boolean;
  matched_bus_count: number;
  unmatched_bus_count: number;
  coverage_percent: number;
  warnings: string[];
  // Operational Context Inspector fields — the same parsed records Preview
  // already computed, carried through unchanged for presentation-only use
  // (psse-integration-module.md §8.9e). `base_mva` is best-effort and may
  // be `null`, same as `raw_version`.
  source_file_reference: string;
  base_mva: number | null;
  buses: ParsedBusRow[];
  branches: ParsedBranchRow[];
  transformers: ParsedTransformerRow[];
  loads: ParsedLoadRow[];
  generators: ParsedGeneratorRow[];
  // RAW File Information (Phase 7 discovery-support enhancement) — header
  // metadata read directly off the parsed RAW case, for engineering
  // visibility only; never used in any calculation. All three are
  // best-effort and may be `null`, same as `raw_version`.
  frequency_hz: number | null;
  case_description: string | null;
  raw_created: string | null;
  // Load-only Snapshot Synchronisation validation (Phase 7B) — `null` for
  // FULL_TOPOLOGY_WITH_LOAD, and for LOAD_ONLY when no Current
  // TopologyVersion exists yet to synchronise against.
  sync_validation: LoadSyncValidationSummary | null;
}

/** One Bus Number present on both the active topology and the incoming
 * load-only case's own bus references, with a differing Bus Name and/or
 * nominal voltage (Phase 7B, EDR-007 Engineering Principle 12). Reported
 * for engineering review — never auto-resolved. */
export interface BusIdentityMismatchRow {
  bus_number: number;
  active_bus_name: string | null;
  incoming_bus_name: string | null;
  active_base_kv: number;
  incoming_base_kv: number;
  mismatch_reason: string;
}

/** Load-only Snapshot Synchronisation validation summary (Phase 7B,
 * EDR-007 Engineering Principle 12 — Bus Number is the sole correlation
 * key). */
export interface LoadSyncValidationSummary {
  total_load_records: number;
  total_distinct_load_buses: number;
  matched_load_buses: number;
  unmatched_load_buses: number;
  missing_topology_buses: number;
  identity_mismatch_buses: number;
  unmatched_load_bus_numbers: number[];
  missing_topology_bus_numbers: number[];
  identity_mismatches: BusIdentityMismatchRow[];
}

/** One category of Commit engineering findings, aggregated (Phase 6.1
 * engineering presentation refinement) — never a new engineering fact,
 * only a grouping of `BatchSummary.warnings`' own messages by the
 * category each was already known to be at the point it was recorded. */
export type FindingCategory =
  | "unmatched_bus"
  | "unmatched_branch_reference"
  | "unmatched_transformer_reference"
  | "unmatched_load_bus"
  | "missing_topology_load_bus"
  | "load_bus_identity_mismatch"
  | "unparsed_data_line"
  | "unrecognized_section";

export type FindingGroupBucket = "engineering_review_required" | "parser_notices" | "informational";

export interface FindingGroup {
  category: FindingCategory;
  group: FindingGroupBucket;
  count: number;
  summary: string;
  details: string[];
}

export interface BatchSummary {
  batch_id: string;
  source_file_reference: string;
  imported_by: UserSummary;
  import_type: ImportType;
  status: BatchStatus;
  computed_signature: string | null;
  topology_version_id: string | null;
  load_snapshot_id: string | null;
  warnings: { message: string }[];
  fatal_error: string | null;
  created_at: string;
  finding_groups: FindingGroup[];
  // Registry matching counts (Phase 6.1) — populated only for a single
  // batch's own detail view; `null` for list rows.
  matched_count: number | null;
  unmatched_count: number | null;
  coverage_percent: number | null;
}

export interface BatchPage {
  items: BatchSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface ActivateRequest {
  change_reason: string;
}

export interface TopologyVersionSummary {
  topology_version_id: string;
  signature: string;
  status: VersionStatus;
  created_from_batch_id: string;
  promoted_at: string | null;
  superseded_at: string | null;
  created_at: string;
  bus_count: number;
  branch_count: number;
  transformer_count: number;
}

export interface TopologyVersionPage {
  items: TopologyVersionSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface LoadSnapshotSummary {
  load_snapshot_id: string;
  topology_version_id: string;
  status: VersionStatus;
  promoted_at: string | null;
  superseded_at: string | null;
  created_at: string;
  load_count: number;
  generator_count: number;
}

export interface LoadSnapshotPage {
  items: LoadSnapshotSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface CurrentStatus {
  current_topology_version: TopologyVersionSummary | null;
  current_load_snapshot: LoadSnapshotSummary | null;
}

export interface EquipmentTopologyMapEntry {
  map_id: string;
  topology_version_id: string;
  circuit_terminal_id: string;
  circuit_id: string;
  circuit_bay_number: string;
  substation_mnemonic: string;
  topology_branch_id: number | null;
  topology_transformer_id: number | null;
  match_outcome: MatchOutcome;
  discrepancy_resolution: DiscrepancyResolution | null;
  resolved_by: UserSummary | null;
  resolved_at: string | null;
  created_at: string;
}

export interface EquipmentTopologyMapPage {
  items: EquipmentTopologyMapEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface DiscrepancyResolveRequest {
  resolution: DiscrepancyResolution;
  change_reason: string;
}

export interface CircuitCorrelation {
  circuit_id: string;
  topology_version_id: string;
  terminals: EquipmentTopologyMapEntry[];
  fully_resolved: boolean;
}

// --- Correlated Operational Model (Phase 7C) -----------------------------
//
// Read models only — never a new source of truth. The preferred
// engineering-consumption surface for future Defence Scheme modules,
// dashboards, and analytics.

export interface OperationalBusView {
  topology_version_id: string;
  bus_number: number;
  bus_name: string | null;
  bus_classification: BusClassification;
  in_service: boolean | null;
  substation_id: string | null;
  substation_mnemonic: string | null;
  voltage_yard_id: string | null;
  correlation_status: CorrelationStatus;
}

export interface OperationalBusViewPage {
  items: OperationalBusView[];
  page: number;
  page_size: number;
  total: number;
}

/** Result of an explicit Bus -> Substation Registry correlation refresh
 * (Phase 7D). Updates only the correlation link, never topology facts,
 * RAW-derived operational data, or Engineering Registry records. */
export interface BusCorrelationRefreshSummary {
  topology_version_id: string;
  buses_processed: number;
  buses_correlated: number;
  buses_unmatched: number;
  buses_outside_scope: number;
  updated_count: number;
}

export interface OperationalBranchView {
  topology_version_id: string;
  topology_branch_id: number;
  from_bus_number: number;
  to_bus_number: number;
  ckt_id: string;
  in_service: boolean | null;
  circuit_id: string | null;
  circuit_bay_number: string | null;
  correlation_status: CorrelationStatus;
}

export interface OperationalBranchViewPage {
  items: OperationalBranchView[];
  page: number;
  page_size: number;
  total: number;
}

export interface OperationalTransformerView {
  topology_version_id: string;
  topology_transformer_id: number;
  from_bus_number: number;
  to_bus_number: number;
  tertiary_bus_number: number | null;
  ckt_id: string;
  in_service: boolean | null;
  circuit_id: string | null;
  circuit_bay_number: string | null;
  correlation_status: CorrelationStatus;
}

export interface OperationalTransformerViewPage {
  items: OperationalTransformerView[];
  page: number;
  page_size: number;
  total: number;
}

export interface OperationalLoadView {
  load_snapshot_id: string;
  bus_number: number;
  load_id: string;
  p_mw: number;
  q_mvar: number;
  owner: number | null;
  load_category: string | null;
  substation_id: string | null;
  substation_mnemonic: string | null;
  voltage_yard_id: string | null;
  relevance_classification: string | null;
  correlation_status: CorrelationStatus;
}

export interface OperationalLoadViewPage {
  items: OperationalLoadView[];
  page: number;
  page_size: number;
  total: number;
}

export interface JobStatus {
  job_id: string;
  status: JobRunStatus;
  result: PreviewResult | BatchSummary | null;
  error: string | null;
}

export interface JobSubmitted {
  job_id: string;
}

/**
 * Commit's response shape depends on the backend's configured execution
 * mode (Phase 6 — Execution Engine, docs/architecture/psse-integration
 * -module.md §8.9c) — the frontend does not know or choose which: Direct
 * mode (default) returns the completed `BatchSummary` immediately;
 * Queue mode returns a `JobSubmitted` job id to poll, unchanged from
 * before this refactor. Discriminate with `"batch_id" in response`.
 */
export type CommitSubmission = BatchSummary | JobSubmitted;
