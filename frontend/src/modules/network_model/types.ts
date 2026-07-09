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

import type {
  OperationalBranchView,
  OperationalTransformerView,
  OperationalBusView,
} from "../psse_integration/types";

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
  /** Phase 7E, Snapshot Awareness — selects a specific Operational
   * Snapshot to traverse; omitted means "whichever TopologyVersion is
   * currently Current." */
  topology_version_id?: string | null;
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
  /** Phase 7E — the Operational Snapshot actually traversed, always
   * resolved and reported explicitly. */
  topology_version_id: string;
}

// --- Phase 7F — Operational Snapshot Verification Workspace -----------------------
//
// `OperationalBusView`/`OperationalBranchView`/`OperationalTransformerView`
// are imported from `psse_integration`, never redefined here — this
// workspace is the first concrete implementation of the Operational
// Projections architecture (docs/architecture/operational-correlation-
// architecture.md §4.1, §4.2): it presents one traversal's Correlated
// Operational Model result at Bus, Switchyard, and Substation granularity,
// reusing the same view models Phase 7C already built.

export interface SnapshotSummary {
  topology_version_id: string | null;
  topology_version_status: string | null;
  load_snapshot_id: string | null;
  load_snapshot_status: string | null;
  import_date: string | null;
  bus_count: number;
  branch_count: number;
  transformer_count: number;
  load_count: number;
  generator_count: number;
}

export interface PathVerificationRequest {
  start_substation_id: string;
  start_voltage_yard_id?: string | null;
  max_depth?: number | null;
  topology_version_id?: string | null;
}

export interface PathStep {
  depth: number;
  from_bus_number: number;
  from_bus_name: string | null;
  to_bus_number: number;
  to_bus_name: string | null;
  edge_type: "BRANCH" | "TRANSFORMER";
  ckt_id: string;
  topology_branch_id: number | null;
  topology_transformer_id: number | null;
}

export interface PathBus {
  depth: number;
  base_kv: number;
  bus: OperationalBusView;
}

export interface TraversalStatistics {
  operational_buses_traversed: number;
  operational_branches_traversed: number;
  operational_transformers_traversed: number;
  operational_switchyards_traversed: number;
  registered_substations_correlated: number;
  registered_switchyards_correlated: number;
}

export interface CorrelationCounts {
  total: number;
  correlated: number;
  unmatched: number;
  outside_scope: number;
}

export interface CorrelationSummary {
  bus: CorrelationCounts;
  branch: CorrelationCounts;
  transformer: CorrelationCounts;
}

export interface BusProjectionEntry {
  bus_number: number;
  bus_name: string | null;
  depth: number;
}

export interface SwitchyardProjectionEntry {
  substation_id: string;
  substation_mnemonic: string;
  base_kv: number;
  voltage_yard_id: string | null;
  depth: number;
  bus_count: number;
}

export interface OperationalProjections {
  bus_projection: BusProjectionEntry[];
  switchyard_projection: SwitchyardProjectionEntry[];
  substation_projection: ReachableSubstation[];
}

export interface TraversalVerificationResult {
  start_substation_id: string;
  start_voltage_yard_id: string | null;
  topology_version_id: string;
  path_steps: PathStep[];
  buses: PathBus[];
  branches: OperationalBranchView[];
  transformers: OperationalTransformerView[];
  statistics: TraversalStatistics;
  correlation_summary: CorrelationSummary;
  projections: OperationalProjections;
}
