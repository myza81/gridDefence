import { apiClient } from "../../api/client";
import type {
  CircuitAuditLogPage,
  CircuitCreate,
  CircuitDetail,
  CircuitPage,
  CircuitStatusChange,
  CircuitTerminalAdd,
  CircuitTerminalIdentity,
  CircuitTerminalSummary,
  CircuitTerminalUpdate,
  CircuitUpdate,
  TransformerAuditLogPage,
  TransformerCreate,
  TransformerDetail,
  TransformerPage,
  TransformerTerminalIdentity,
  TransformerUpdate,
  VoltageYardAuditLogPage,
  VoltageYardCreate,
  VoltageYardSummary,
  VoltageYardUpdate,
} from "./types";

export interface CircuitListFilters {
  page?: number;
  page_size?: number;
  substation_id?: string;
  voltage_level_id?: number;
  line_type_id?: number;
  operational_status_id?: number;
  is_interconnector?: boolean;
  search?: string;
  // Deletion/correction policy (Phase 3 follow-up) — Entered-in-Error
  // circuits are excluded by default; this opts back in for an
  // audit-facing "show corrected records" view.
  include_entered_in_error?: boolean;
}

export interface TransformerListFilters {
  page?: number;
  page_size?: number;
  substation_id?: string;
  operational_status_id?: number;
  search?: string;
  include_entered_in_error?: boolean;
}

export interface VoltageYardListFilters {
  substation_id?: string;
  include_entered_in_error?: boolean;
}

function buildQuery<T extends object>(filters: T): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** Endpoint shapes per docs/architecture/equipment-registry-module.md §12, §7.5a. */
export const equipmentRegistryApi = {
  listCircuits: (filters: CircuitListFilters = {}) =>
    apiClient.get<CircuitPage>(`/api/v1/circuits${buildQuery(filters)}`),
  getCircuit: (circuitId: string) => apiClient.get<CircuitDetail>(`/api/v1/circuits/${circuitId}`),
  createCircuit: (payload: CircuitCreate) =>
    apiClient.post<CircuitDetail>("/api/v1/circuits", payload),
  updateCircuit: (circuitId: string, payload: CircuitUpdate) =>
    apiClient.patch<CircuitDetail>(`/api/v1/circuits/${circuitId}`, payload),
  changeStatus: (circuitId: string, payload: CircuitStatusChange) =>
    apiClient.post<CircuitDetail>(`/api/v1/circuits/${circuitId}/status`, payload),
  listTerminals: (circuitId: string) =>
    apiClient.get<CircuitTerminalSummary[]>(`/api/v1/circuits/${circuitId}/terminals`),
  addTerminal: (circuitId: string, payload: CircuitTerminalAdd) =>
    apiClient.post<CircuitDetail>(`/api/v1/circuits/${circuitId}/terminals`, payload),
  updateTerminal: (circuitId: string, terminalId: string, payload: CircuitTerminalUpdate) =>
    apiClient.patch<CircuitDetail>(
      `/api/v1/circuits/${circuitId}/terminals/${terminalId}`,
      payload,
    ),
  listAuditLog: (circuitId: string, page = 1, pageSize = 50) =>
    apiClient.get<CircuitAuditLogPage>(
      `/api/v1/circuits/${circuitId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
  listVoltageYards: (filters: VoltageYardListFilters = {}) =>
    apiClient.get<VoltageYardSummary[]>(`/api/v1/voltage-yards${buildQuery(filters)}`),
  createVoltageYard: (payload: VoltageYardCreate) =>
    apiClient.post<VoltageYardSummary>("/api/v1/voltage-yards", payload),
  updateVoltageYard: (voltageYardId: string, payload: VoltageYardUpdate) =>
    apiClient.patch<VoltageYardSummary>(`/api/v1/voltage-yards/${voltageYardId}`, payload),
  listVoltageYardAuditLog: (voltageYardId: string, page = 1, pageSize = 50) =>
    apiClient.get<VoltageYardAuditLogPage>(
      `/api/v1/voltage-yards/${voltageYardId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
  listTransformers: (filters: TransformerListFilters = {}) =>
    apiClient.get<TransformerPage>(`/api/v1/transformers${buildQuery(filters)}`),
  getTransformer: (transformerId: string) =>
    apiClient.get<TransformerDetail>(`/api/v1/transformers/${transformerId}`),
  createTransformer: (payload: TransformerCreate) =>
    apiClient.post<TransformerDetail>("/api/v1/transformers", payload),
  updateTransformer: (transformerId: string, payload: TransformerUpdate) =>
    apiClient.patch<TransformerDetail>(`/api/v1/transformers/${transformerId}`, payload),
  listTransformerAuditLog: (transformerId: string, page = 1, pageSize = 50) =>
    apiClient.get<TransformerAuditLogPage>(
      `/api/v1/transformers/${transformerId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
  listTransformerTerminalIdentities: () =>
    apiClient.get<TransformerTerminalIdentity[]>("/api/v1/transformer-terminals"),
  listCircuitTerminalIdentities: () =>
    apiClient.get<CircuitTerminalIdentity[]>("/api/v1/circuit-terminals"),
};
