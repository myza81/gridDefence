/**
 * Mirrors backend/app/reference_data/schemas.py. Core Platform reference
 * data — not owned by any single business module (substation-registry.md
 * §4: "modeled as small, independently managed tables"), so this lives
 * alongside modules/, not inside modules/substation_registry/.
 */

export interface VoltageLevelSummary {
  voltage_level_id: number;
  label: string;
  nominal_kv: number;
  sort_order: number;
}

export interface RegionSummary {
  region_id: number;
  code: string;
  label: string;
}

export interface StateSummary {
  state_id: number;
  code: string;
  label: string;
}

export interface GridOwnerSummary {
  grid_owner_id: number;
  code: string;
  label: string;
}

export interface OperationalStatusSummary {
  operational_status_id: number;
  code: string;
  label: string;
  is_terminal: boolean;
}

export interface LineTypeSummary {
  line_type_id: number;
  code: string;
  label: string;
}

export interface TransformerBreakerNumberingConventionSummary {
  convention_id: number;
  hv_voltage_level_id: number;
  lv_voltage_level_id: number;
  side: "HV" | "LV";
  pattern: string | null;
  is_standard: boolean;
  notes: string | null;
}
