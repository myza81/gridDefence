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

/** One PSS/E bus record, exactly as the parser produced it — no
 * engineering translation, no registry correlation (Operational Context
 * Inspector). Mirrors backend `ParsedBusRow`/`raw_parser.ParsedBus`
 * field-for-field. */
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
}

export interface ParsedLoadRow {
  bus_number: number;
  load_id: string;
  status: boolean;
  p_mw: number;
  q_mvar: number;
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
