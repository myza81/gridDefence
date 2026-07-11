/**
 * Mirrors backend/app/modules/sensitive_customer_registry/schemas.py.
 * The frontend performs no authoritative engineering logic (CLAUDE.md A12) —
 * these types exist only to describe the API contract the backend already
 * enforces. See docs/architecture/sensitive-customer-registry-module.md
 * (ADR-012) and docs/architecture/sensitive-customer-registry-implementation-spec.md.
 */

export type LifecycleStatus = "ACTIVE" | "ARCHIVED" | "ENTERED_IN_ERROR";

// Correction 4, generalised by ADR-013 — three independently-surfaced
// facts, never conflated with lifecycle_status:
//   NOT_ASSIGNED — no Transformer Terminal is currently associated
//                  (facility-level aggregate only — never used on a
//                  single association, since a row's existence means it
//                  was assigned).
//   RESOLVED     — the associated terminal is recorded and Equipment
//                  Registry currently resolves it.
//   UNRESOLVED   — the associated terminal is recorded but cannot
//                  currently be resolved (stale reference). The facility
//                  is never omitted from any list/detail view as a
//                  result — this field surfaces the condition instead.
//
// Since ADR-013, a facility may have several associations, each
// independently RESOLVED or UNRESOLVED. The facility-level aggregate
// (`SensitiveFacilitySummary.transformer_terminal_resolution`) is:
// NOT_ASSIGNED if there are no associations; RESOLVED if every
// association resolves; UNRESOLVED if at least one does not.
export type TransformerTerminalResolution = "NOT_ASSIGNED" | "RESOLVED" | "UNRESOLVED";

// Per-association resolution never reports NOT_ASSIGNED — a row only
// exists because it was assigned.
export type AssociationResolution = "RESOLVED" | "UNRESOLVED";

export interface SensitiveFacilityTerminalAssociation {
  transformer_terminal_id: string;
  resolution: AssociationResolution;
  substation_id: string | null;
  substation_mnemonic: string | null;
  substation_official_name: string | null;
  voltage_level_label: string | null;
  bay_label: string | null;
  side: string | null;
}

export interface FacilitySectorSummary {
  id: number;
  code: string;
  label: string;
  sort_order: number;
  description: string | null;
  is_active: boolean;
}

export interface SensitivityClassificationSummary {
  id: number;
  code: string;
  label: string;
  sort_order: number;
  description: string | null;
  is_active: boolean;
}

export interface FacilitySectorCreate {
  code: string;
  label: string;
  sort_order?: number;
  description?: string | null;
}

export interface FacilitySectorUpdate {
  label?: string;
  sort_order?: number;
  description?: string | null;
  is_active?: boolean;
  change_reason?: string | null;
}

export interface SensitivityClassificationCreate {
  code: string;
  label: string;
  sort_order?: number;
  description?: string | null;
}

export interface SensitivityClassificationUpdate {
  label?: string;
  sort_order?: number;
  description?: string | null;
  is_active?: boolean;
  change_reason?: string | null;
}

export interface SensitiveFacilityCreate {
  name: string;
  facility_sector_id: number;
  sensitivity_classification_id: number;
  transformer_terminal_ids?: string[];
  remarks?: string | null;
}

export interface SensitiveFacilityUpdate {
  name?: string;
  facility_sector_id?: number;
  sensitivity_classification_id?: number;
  remarks?: string | null;
  change_reason?: string | null;
}

/** Replaces the full set of a facility's currently associated Transformer
 * Terminals in one call (ADR-013) — never a partial add/remove of one at
 * a time. `change_reason` is mandatory whenever the set actually changes;
 * a no-op call (target set equals current set) requires no reason. */
export interface SensitiveFacilityTerminalsUpdate {
  transformer_terminal_ids: string[];
  change_reason?: string | null;
}

export interface SensitiveFacilityLifecycleRequest {
  change_reason?: string | null;
}

export interface UserSummary {
  user_id: string;
  username: string;
  display_name: string;
  email: string | null;
}

export interface SensitiveFacilitySummary {
  id: string;
  name: string;
  facility_sector: FacilitySectorSummary;
  sensitivity_classification: SensitivityClassificationSummary;
  transformer_terminals: SensitiveFacilityTerminalAssociation[];
  transformer_terminal_resolution: TransformerTerminalResolution;
  lifecycle_status: LifecycleStatus;
  updated_at: string;
}

export interface SensitiveFacilityPage {
  items: SensitiveFacilitySummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface SensitiveFacilityDetail {
  id: string;
  name: string;
  facility_sector: FacilitySectorSummary;
  sensitivity_classification: SensitivityClassificationSummary;
  transformer_terminals: SensitiveFacilityTerminalAssociation[];
  transformer_terminal_resolution: TransformerTerminalResolution;
  lifecycle_status: LifecycleStatus;
  remarks: string | null;
  created_at: string;
  updated_at: string;
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
}

export interface SensitiveFacilityAuditLogEntry {
  log_id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface SensitiveFacilityAuditLogPage {
  items: SensitiveFacilityAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface BatchLookupResponse {
  results: Record<string, SensitiveFacilitySummary[]>;
}

export interface SensitiveFacilitySummaryCounts {
  active_count: number;
  archived_count: number;
  entered_in_error_count: number;
  by_sector: Record<string, number>;
  by_sensitivity_classification: Record<string, number>;
  unresolved_terminal_count: number;
}

export interface FacilityListFilters {
  page?: number;
  page_size?: number;
  facility_sector_id?: number;
  sensitivity_classification_id?: number;
  lifecycle_status?: LifecycleStatus;
  transformer_terminal_id?: string;
  transformer_terminal_resolution?: TransformerTerminalResolution;
  substation_id?: string;
}
