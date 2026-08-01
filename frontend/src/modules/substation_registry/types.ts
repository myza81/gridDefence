/**
 * Mirrors backend/app/modules/substation_registry/schemas.py. The frontend
 * performs no authoritative engineering logic (CLAUDE.md A12) — these types
 * exist only to describe the API contract the backend already enforces.
 */

import type { UserSummary } from "../iam/types";

export interface SubstationSummary {
  substation_id: string;
  mnemonic: string;
  official_name: string;
  region_id: number;
  gm_zone_id: number;
  // State is optional (ADR-026) — `null` when no State is assigned.
  state_id: number | null;
  grid_owner_id: number;
  operational_status_id: number;
  psse_bus_number: number | null;
}

export interface SubstationPage {
  items: SubstationSummary[];
  page: number;
  page_size: number;
  total: number;
}

/** Lightweight geographic projection for the map (Phase E.1). The authoritative
 *  coordinate is the Substation's own latitude/longitude (ADR-008). */
export interface SubstationMapFeature {
  substation_id: string;
  mnemonic: string;
  official_name: string;
  operational_status_id: number;
  region_id: number;
  gm_zone_id: number;
  state_id: number | null;
  grid_owner_id: number;
  latitude: number | null;
  longitude: number | null;
  coordinate_status: "present" | "missing";
}

export interface SubstationMapResponse {
  items: SubstationMapFeature[];
  mapped_count: number;
  missing_coordinate_count: number;
  total: number;
}

export interface SubstationDetail {
  substation_id: string;
  mnemonic: string;
  official_name: string;
  region_id: number;
  gm_zone_id: number;
  // State is optional (ADR-026) — `null` when no State is assigned.
  state_id: number | null;
  grid_owner_id: number;
  operational_status_id: number;
  psse_bus_number: number | null;
  latitude: number | null;
  longitude: number | null;
  commissioned_date: string | null;
  remarks: string | null;
  created_at: string;
  updated_at: string;
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
}

export interface SubstationCreate {
  mnemonic: string;
  official_name: string;
  region_id: number;
  // GM Zone — organizational maintenance responsibility, independent of
  // region_id. Required, exactly like region_id — every Substation shall
  // reference exactly one GM Zone.
  gm_zone_id: number;
  // State is an administrative attribute, not part of engineering
  // identity — optional (ADR-026). Omit it, or send null/a value.
  state_id?: number | null;
  grid_owner_id: number;
  operational_status_id: number;
  psse_bus_number?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  commissioned_date?: string | null;
  remarks?: string | null;
}

export interface SubstationUpdate {
  mnemonic?: string;
  official_name?: string;
  region_id?: number;
  gm_zone_id?: number;
  // State is optional (ADR-026): omit to leave unchanged, send `null` to
  // clear it, or send a value to set it.
  state_id?: number | null;
  grid_owner_id?: number;
  psse_bus_number?: number | null;
  latitude?: number | null;
  longitude?: number | null;
  commissioned_date?: string | null;
  remarks?: string | null;
}

export interface SubstationStatusChange {
  operational_status_id: number;
  change_reason?: string | null;
}

export interface SubstationAliasSummary {
  alias_id: number;
  alias_mnemonic: string | null;
  alias_name: string | null;
  valid_from: string;
  valid_to: string | null;
}

export interface SubstationAuditLogEntry {
  log_id: number;
  field_name: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface SubstationAuditLogPage {
  items: SubstationAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}
