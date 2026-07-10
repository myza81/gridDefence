/**
 * Mirrors backend/app/modules/automatic_load_shedding_functionality/schemas.py.
 * The frontend performs no authoritative engineering logic (CLAUDE.md A12) —
 * these types exist only to describe the API contract the backend already
 * enforces. See docs/architecture/automatic-load-shedding-functionality-
 * registry-module.md (ADR-011).
 */

export type TargetType = "CIRCUIT_TERMINAL" | "TRANSFORMER_TERMINAL";
// Status Model Refinement (engineering refinement) — the status an
// engineer sees is always exactly one of these three:
//   AVAILABLE      — functionality exists, not currently referenced by any
//                     active UFLS/UVLS scheme. Computed by the backend,
//                     never stored, never settable by the frontend.
//   ASSIGNED       — functionality exists, currently referenced by at
//                     least one active UFLS and/or UVLS scheme. Computed,
//                     never manually editable.
//   DECOMMISSIONED — functionality permanently removed. A terminal,
//                     one-way engineering decision.
// The frontend performs no authoritative engineering logic (CLAUDE.md
// A12) — this type only describes the API contract; the backend computes
// every status value it returns.
export type FunctionalityStatus = "AVAILABLE" | "ASSIGNED" | "DECOMMISSIONED";
// EMLS is deliberately never a valid value here — this registry has no
// knowledge of EMLS at all (module document §4, §9 rule 4).
export type SchemeType = "UFLS" | "UVLS";

export interface FunctionalityCreate {
  target_type: TargetType;
  circuit_terminal_id?: string | null;
  transformer_terminal_id?: string | null;
  ufls_function: boolean;
  uvls_function: boolean;
  relay_make?: string | null;
  relay_model?: string | null;
  remarks?: string | null;
}

export interface FunctionalityUpdate {
  ufls_function?: boolean;
  uvls_function?: boolean;
  relay_make?: string | null;
  relay_model?: string | null;
  remarks?: string | null;
  change_reason?: string | null;
}

export interface FunctionalityDecommissionRequest {
  change_reason?: string | null;
}

export interface FunctionalitySummary {
  id: string;
  target_type: TargetType;
  circuit_terminal_id: string | null;
  transformer_terminal_id: string | null;
  substation_id: string;
  substation_mnemonic: string;
  voltage_level_label: string;
  bay_label: string;
  ufls_function: boolean;
  uvls_function: boolean;
  status: FunctionalityStatus;
  updated_at: string;
}

export interface FunctionalityPage {
  items: FunctionalitySummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface UserSummary {
  user_id: string;
  username: string;
  display_name: string;
  email: string | null;
}

export interface FunctionalityDetail {
  id: string;
  target_type: TargetType;
  circuit_terminal_id: string | null;
  transformer_terminal_id: string | null;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  voltage_level_label: string;
  bay_label: string;
  ufls_function: boolean;
  uvls_function: boolean;
  status: FunctionalityStatus;
  relay_make: string | null;
  relay_model: string | null;
  remarks: string | null;
  created_at: string;
  updated_at: string;
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
}

export interface FunctionalityAuditLogEntry {
  log_id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface FunctionalityAuditLogPage {
  items: FunctionalityAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface CandidateTerminal {
  id: string;
  target_type: TargetType;
  circuit_terminal_id: string | null;
  transformer_terminal_id: string | null;
  substation_id: string;
  substation_mnemonic: string;
  voltage_level_label: string;
  bay_label: string;
  ufls_function: boolean;
  uvls_function: boolean;
}

export interface CandidateTerminalList {
  items: CandidateTerminal[];
  total: number;
}

export interface CapabilityCheckResponse {
  capable: boolean;
}

export interface FunctionalityListFilters {
  page?: number;
  page_size?: number;
  target_type?: TargetType;
  ufls_function?: boolean;
  uvls_function?: boolean;
  status_filter?: FunctionalityStatus;
  substation_id?: string;
  voltage_level_id?: number;
}

export interface CandidateFilters {
  scheme_type: SchemeType;
  substation_id?: string;
  target_type?: TargetType;
  voltage_level_id?: number;
}
