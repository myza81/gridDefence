import { apiClient } from "../../api/client";
import type {
  SubstationAuditLogPage,
  SubstationAliasSummary,
  SubstationCreate,
  SubstationDetail,
  SubstationPage,
  SubstationStatusChange,
  SubstationUpdate,
} from "./types";

export interface SubstationListFilters {
  page?: number;
  page_size?: number;
  region_id?: number;
  gm_zone_id?: number;
  state_id?: number;
  grid_owner_id?: number;
  operational_status_id?: number;
  search?: string;
}

function buildQuery(filters: SubstationListFilters): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== "") {
      params.set(key, String(value));
    }
  }
  const query = params.toString();
  return query ? `?${query}` : "";
}

/** Endpoint shapes per docs/architecture/substation-registry.md §13. */
export const substationRegistryApi = {
  listSubstations: (filters: SubstationListFilters = {}) =>
    apiClient.get<SubstationPage>(`/api/v1/substations${buildQuery(filters)}`),
  getSubstation: (substationId: string) =>
    apiClient.get<SubstationDetail>(`/api/v1/substations/${substationId}`),
  createSubstation: (payload: SubstationCreate) =>
    apiClient.post<SubstationDetail>("/api/v1/substations", payload),
  updateSubstation: (substationId: string, payload: SubstationUpdate) =>
    apiClient.patch<SubstationDetail>(`/api/v1/substations/${substationId}`, payload),
  changeStatus: (substationId: string, payload: SubstationStatusChange) =>
    apiClient.post<SubstationDetail>(`/api/v1/substations/${substationId}/status`, payload),
  listAliases: (substationId: string) =>
    apiClient.get<SubstationAliasSummary[]>(`/api/v1/substations/${substationId}/aliases`),
  listAuditLog: (substationId: string, page = 1, pageSize = 50) =>
    apiClient.get<SubstationAuditLogPage>(
      `/api/v1/substations/${substationId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
};
