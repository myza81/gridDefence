/**
 * Mirrors backend/app/modules/network_model/schemas.py. The frontend
 * performs no authoritative engineering logic (CLAUDE.md A12) — these types
 * exist only to describe the API contract the backend already enforces.
 *
 * Presentation note: this module's pages present these shapes using
 * GridDefence's official engineering terminology
 * (docs/engineering/08-engineering-terminology.md) — a `LineBay` (backend
 * name, unchanged here to mirror the API exactly) is always labeled
 * "Line Bay" in the UI, and a `TransformerBay` is always labeled
 * "Transformer Bay". Implementation names (`CircuitTerminal`,
 * `TransformerTerminal`) are never shown to a user.
 */

export interface TerminalOnCircuit {
  circuit_terminal_id: string;
  substation_id: string;
  substation_mnemonic: string;
  voltage_yard_id: string;
  breaker_number: string;
}

export interface ConnectingLine {
  circuit_id: string;
  bay_number: string;
  circuit_name: string;
  voltage_level_label: string;
  line_type_label: string;
  operational_status_code: string;
  is_tee_off: boolean;
  terminals: TerminalOnCircuit[];
}

export interface NeighbourSubstation {
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  via_circuit_id: string;
  via_circuit_name: string;
  via_bay_number: string;
}

export interface ElectricalNeighbour {
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  connecting_line_count: number;
}

export interface SubstationConnectivity {
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  connected_lines: ConnectingLine[];
  neighbours: NeighbourSubstation[];
}

export interface TransformerBay {
  transformer_id: string;
  transformer_number: string;
  generated_short_name: string;
  hv_voltage_level_label: string;
  lv_voltage_level_label: string;
  capacity_mva: number | null;
  operational_status_code: string;
}

export interface LineBay {
  circuit_terminal_id: string;
  circuit_id: string;
  circuit_bay_number: string;
  circuit_name: string;
  breaker_number: string;
  voltage_level_label: string;
  operational_status_code: string;
}

export interface SubstationEquipment {
  substation_id: string;
  substation_mnemonic: string;
  substation_official_name: string;
  transformer_bays: TransformerBay[];
  line_bays: LineBay[];
}

export interface NetworkOverview {
  substation_count: number;
  circuit_count: number;
  tee_off_circuit_count: number;
  transformer_count: number;
}

export interface TraversalRequest {
  start_substation_id: string;
  excluded_circuit_ids?: string[];
  max_depth?: number | null;
}

export interface ReachableSubstation {
  substation_id: string;
  substation_mnemonic: string;
  depth: number;
}

export interface TraversalResult {
  start_substation_id: string;
  excluded_circuit_ids: string[];
  reachable_substations: ReachableSubstation[];
}
