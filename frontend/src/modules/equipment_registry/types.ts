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
  created_at: string;
  updated_at: string;
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
