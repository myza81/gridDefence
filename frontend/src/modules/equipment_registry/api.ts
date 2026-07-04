import { apiClient } from "../../api/client";
import type {
  CircuitAuditLogPage,
  CircuitCreate,
  CircuitDetail,
  CircuitPage,
  CircuitStatusChange,
  CircuitTerminalAdd,
  CircuitTerminalSummary,
  CircuitTerminalUpdate,
  CircuitUpdate,
  VoltageYardCreate,
  VoltageYardSummary,
  VoltageYardUpdate,
} from "./types";

export interface CircuitListFilters {
  page?: number;
  page_size?: number;
  voltage_level_id?: number;
  line_type_id?: number;
  operational_status_id?: number;
  is_interconnector?: boolean;
  search?: string;
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
  listVoltageYards: (substationId?: string) =>
    apiClient.get<VoltageYardSummary[]>(
      `/api/v1/voltage-yards${buildQuery({ substation_id: substationId })}`,
    ),
  createVoltageYard: (payload: VoltageYardCreate) =>
    apiClient.post<VoltageYardSummary>("/api/v1/voltage-yards", payload),
  updateVoltageYard: (voltageYardId: string, payload: VoltageYardUpdate) =>
    apiClient.patch<VoltageYardSummary>(`/api/v1/voltage-yards/${voltageYardId}`, payload),
};
