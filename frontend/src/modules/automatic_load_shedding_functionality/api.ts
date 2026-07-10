import { apiClient } from "../../api/client";
import type {
  CandidateFilters,
  CandidateTerminalList,
  CapabilityCheckResponse,
  FunctionalityAuditLogPage,
  FunctionalityCreate,
  FunctionalityDecommissionRequest,
  FunctionalityDetail,
  FunctionalityListFilters,
  FunctionalityPage,
  FunctionalityUpdate,
  SchemeType,
} from "./types";

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

/** Endpoint shapes per docs/architecture/automatic-load-shedding-
 * functionality-registry-module.md §12 (ADR-011). */
export const automaticLoadSheddingFunctionalityApi = {
  list: (filters: FunctionalityListFilters = {}) =>
    apiClient.get<FunctionalityPage>(
      `/api/v1/automatic-load-shedding-functionality${buildQuery(filters)}`,
    ),
  create: (payload: FunctionalityCreate) =>
    apiClient.post<FunctionalityDetail>("/api/v1/automatic-load-shedding-functionality", payload),
  get: (functionalityId: string) =>
    apiClient.get<FunctionalityDetail>(
      `/api/v1/automatic-load-shedding-functionality/${functionalityId}`,
    ),
  update: (functionalityId: string, payload: FunctionalityUpdate) =>
    apiClient.patch<FunctionalityDetail>(
      `/api/v1/automatic-load-shedding-functionality/${functionalityId}`,
      payload,
    ),
  decommission: (functionalityId: string, payload: FunctionalityDecommissionRequest) =>
    apiClient.post<FunctionalityDetail>(
      `/api/v1/automatic-load-shedding-functionality/${functionalityId}/decommission`,
      payload,
    ),
  listAuditLog: (functionalityId: string, page = 1, pageSize = 50) =>
    apiClient.get<FunctionalityAuditLogPage>(
      `/api/v1/automatic-load-shedding-functionality/${functionalityId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
  listCandidates: (filters: CandidateFilters) =>
    apiClient.get<CandidateTerminalList>(
      `/api/v1/automatic-load-shedding-functionality/candidates${buildQuery(filters)}`,
    ),
  checkCapability: (
    schemeType: SchemeType,
    terminal: { circuit_terminal_id?: string; transformer_terminal_id?: string },
  ) =>
    apiClient.get<CapabilityCheckResponse>(
      `/api/v1/automatic-load-shedding-functionality/capability-check${buildQuery({
        scheme_type: schemeType,
        ...terminal,
      })}`,
    ),
};
