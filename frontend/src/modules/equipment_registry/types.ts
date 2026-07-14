/**
 * Mirrors backend/app/modules/equipment_registry/schemas.py. The frontend
 * performs no authoritative engineering logic (CLAUDE.md A12) — these types
 * exist only to describe the API contract the backend already enforces.
 */

import type { UserSummary } from "../iam/types";

export interface VoltageYardCreate {
  substation_id: string;
  voltage_level_id: number;
  // Yard-level metadata (Phase 3 UAT follow-up) — optional, and
  // deliberately never on Substation; a multi-voltage site may have yards
  // commissioned at different dates with slightly different GIS
  // coordinates.
  commissioning_date?: string | null;
  latitude?: number | null;
  longitude?: number | null;
}

export interface VoltageYardUpdate {
  commissioning_date?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  // Deletion/correction policy (Phase 3 follow-up) — corrects a
  // mistakenly-created switchyard via ENTERED_IN_ERROR, never a hard
  // delete. change_reason is optional context for the audit trail.
  operational_status_id?: number;
  change_reason?: string | null;
}

export interface VoltageYardSummary {
  voltage_yard_id: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  voltage_level_id: number;
  voltage_level_label: string;
  display_label: string;
  commissioning_date: string | null;
  latitude: number | null;
  longitude: number | null;
  operational_status_id: number;
}

export interface VoltageYardAuditLogEntry {
  log_id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface VoltageYardAuditLogPage {
  items: VoltageYardAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}

export interface CircuitTerminalCreate {
  voltage_yard_id: string;
  breaker_number: string;
  commissioning_date?: string | null;
  remarks?: string | null;
}

export interface CircuitCreate {
  bay_number: string;
  voltage_level_id: number;
  line_type_id: number;
  operational_status_id: number;
  is_interconnector: boolean;
  remarks?: string | null;
  terminals: CircuitTerminalCreate[];
}

export interface CircuitUpdate {
  bay_number?: string;
  voltage_level_id?: number;
  line_type_id?: number;
  is_interconnector?: boolean;
  remarks?: string | null;
}

export interface CircuitStatusChange {
  operational_status_id: number;
  change_reason?: string | null;
}

export interface CircuitTerminalAdd {
  voltage_yard_id: string;
  breaker_number: string;
  commissioning_date?: string | null;
  remarks?: string | null;
}

export interface CircuitTerminalUpdate {
  breaker_number?: string;
  commissioning_date?: string | null;
  remarks?: string | null;
  // Deletion/correction policy (Phase 3 follow-up) — corrects a
  // mistakenly-added terminal via ENTERED_IN_ERROR, never a hard delete;
  // never rejected by the backend, even below the two-active-terminal
  // completeness rule (that is enforced instead at circuit activation).
  operational_status_id?: number;
}

export interface CircuitTerminalSummary {
  circuit_terminal_id: string;
  voltage_yard_id: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  voltage_level_id: number;
  voltage_level_label: string;
  breaker_number: string;
  commissioning_date: string | null;
  remarks: string | null;
  operational_status_id: number;
  created_at: string;
  updated_at: string;
}

/** Full composed identity of one Circuit Terminal, across every substation —
 * mirrors `TransformerTerminalIdentity` exactly (below), added for the same
 * cross-network-picker reason (Foundation Hardening Sprint A.1's Boundary
 * Pocket diagnostic evaluator). Returned unpaginated by
 * `GET /circuit-terminals` — exposed as its own top-level resource,
 * alongside the existing path-nested `/circuits/{id}/terminals`
 * (`CircuitTerminalSummary`, above), which remains unchanged. */
export interface CircuitTerminalIdentity {
  circuit_terminal_id: string;
  circuit_id: string;
  circuit_name: string;
  bay_number: string;
  breaker_number: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  voltage_level_id: number;
  voltage_level_label: string;
}

export interface CircuitSummary {
  circuit_id: string;
  bay_number: string;
  circuit_name: string;
  voltage_level_id: number;
  line_type_id: number;
  operational_status_id: number;
  is_interconnector: boolean;
  terminal_count: number;
}

export interface CircuitPage {
  items: CircuitSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface CircuitDetail {
  circuit_id: string;
  bay_number: string;
  circuit_name: string;
  voltage_level_id: number;
  line_type_id: number;
  operational_status_id: number;
  is_interconnector: boolean;
  remarks: string | null;
  created_at: string;
  updated_at: string;
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
  terminals: CircuitTerminalSummary[];
}

export interface CircuitAuditLogEntry {
  log_id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface CircuitAuditLogPage {
  items: CircuitAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}

// Transformer Registry (Phase 3.5). A transformer connects exactly two
// switchyards (HV/LV) — see docs/architecture/equipment-registry-module.md's
// Transformer Registry section. `generated_short_name` is computed by the
// backend at read time, never stored (Architecture Decision Gate outcome) —
// it is present on every response shape but never accepted on a request.

export interface TransformerCreate {
  // Substation-first (UAT correction): a transformer is substation-owned
  // equipment, never modeled as spanning two substations. Both switchyards
  // below must belong to this same substation — enforced by the backend.
  substation_id: string;
  transformer_number: string;
  hv_switchyard_id: string;
  hv_breaker_number: string;
  lv_switchyard_id: string;
  lv_breaker_number: string;
  capacity_mva?: number | null;
  commissioning_date?: string | null;
  operational_status_id: number;
  transformer_type?: string | null;
  manufacturer?: string | null;
  remarks?: string | null;
}

export interface TransformerUpdate {
  transformer_number?: string;
  hv_breaker_number?: string;
  lv_breaker_number?: string;
  capacity_mva?: number | null;
  commissioning_date?: string | null;
  operational_status_id?: number;
  transformer_type?: string | null;
  manufacturer?: string | null;
  remarks?: string | null;
}

export interface TransformerTerminalSummary {
  transformer_terminal_id: string;
  side: "HV" | "LV";
  voltage_yard_id: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  voltage_level_id: number;
  voltage_level_label: string;
  breaker_number: string;
}

/** Full composed identity of one Transformer Terminal, across every
 * substation — used by cross-module pickers (e.g. the Sensitive Customer
 * Registry's multi-select, ADR-013) that must not require a substation or
 * transformer to be chosen first. Returned unpaginated by
 * `GET /transformer-terminals` — exposed as its own top-level resource,
 * mirroring `VoltageYard`'s own `/voltage-yards` precedent, not nested
 * under `/transformers/{id}/terminals` (Phase 3.7 UAT refinement). */
export interface TransformerTerminalIdentity {
  transformer_terminal_id: string;
  transformer_id: string;
  generated_short_name: string;
  transformer_number: string;
  side: "HV" | "LV";
  breaker_number: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  voltage_level_id: number;
  voltage_level_label: string;
}

export interface TransformerSummary {
  transformer_id: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  transformer_number: string;
  generated_short_name: string;
  hv_voltage_level_label: string;
  lv_voltage_level_label: string;
  capacity_mva: number | null;
  operational_status_id: number;
}

export interface TransformerPage {
  items: TransformerSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface TransformerDetail {
  transformer_id: string;
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  transformer_number: string;
  generated_short_name: string;
  capacity_mva: number | null;
  commissioning_date: string | null;
  operational_status_id: number;
  transformer_type: string | null;
  manufacturer: string | null;
  remarks: string | null;
  created_at: string;
  updated_at: string;
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
  terminals: TransformerTerminalSummary[];
}

export interface TransformerAuditLogEntry {
  log_id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface TransformerAuditLogPage {
  items: TransformerAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}
