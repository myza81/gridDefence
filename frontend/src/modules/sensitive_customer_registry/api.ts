import { apiClient } from "../../api/client";
import type {
  BatchLookupResponse,
  FacilityListFilters,
  FacilitySectorCreate,
  FacilitySectorSummary,
  FacilitySectorUpdate,
  SensitiveFacilityAuditLogPage,
  SensitiveFacilityCreate,
  SensitiveFacilityDetail,
  SensitiveFacilityLifecycleRequest,
  SensitiveFacilityPage,
  SensitiveFacilitySummaryCounts,
  SensitiveFacilityTerminalsUpdate,
  SensitiveFacilityUpdate,
  SensitivityClassificationCreate,
  SensitivityClassificationSummary,
  SensitivityClassificationUpdate,
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

/** Endpoint shapes per docs/architecture/sensitive-customer-registry-
 * implementation-spec.md §10 (ADR-012). */
export const sensitiveCustomerRegistryApi = {
  listFacilities: (filters: FacilityListFilters = {}) =>
    apiClient.get<SensitiveFacilityPage>(
      `/api/v1/sensitive-customer-registry/facilities${buildQuery(filters)}`,
    ),
  createFacility: (payload: SensitiveFacilityCreate) =>
    apiClient.post<SensitiveFacilityDetail>(
      "/api/v1/sensitive-customer-registry/facilities",
      payload,
    ),
  getFacility: (facilityId: string) =>
    apiClient.get<SensitiveFacilityDetail>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}`,
    ),
  updateFacility: (facilityId: string, payload: SensitiveFacilityUpdate) =>
    apiClient.patch<SensitiveFacilityDetail>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}`,
      payload,
    ),
  setFacilityTerminals: (facilityId: string, payload: SensitiveFacilityTerminalsUpdate) =>
    apiClient.put<SensitiveFacilityDetail>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}/terminals`,
      payload,
    ),
  archiveFacility: (facilityId: string, payload: SensitiveFacilityLifecycleRequest) =>
    apiClient.post<SensitiveFacilityDetail>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}/archive`,
      payload,
    ),
  reactivateFacility: (facilityId: string, payload: SensitiveFacilityLifecycleRequest) =>
    apiClient.post<SensitiveFacilityDetail>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}/reactivate`,
      payload,
    ),
  markFacilityEnteredInError: (facilityId: string, payload: SensitiveFacilityLifecycleRequest) =>
    apiClient.post<SensitiveFacilityDetail>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}/entered-in-error`,
      payload,
    ),
  listAuditLog: (facilityId: string, page = 1, pageSize = 50) =>
    apiClient.get<SensitiveFacilityAuditLogPage>(
      `/api/v1/sensitive-customer-registry/facilities/${facilityId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
  batchLookup: (transformerTerminalIds: string[]) =>
    apiClient.post<BatchLookupResponse>(
      "/api/v1/sensitive-customer-registry/facilities/batch-lookup",
      { transformer_terminal_ids: transformerTerminalIds },
    ),
  getSummary: () =>
    apiClient.get<SensitiveFacilitySummaryCounts>(
      "/api/v1/sensitive-customer-registry/facilities/summary",
    ),
  listFacilitySectors: () =>
    apiClient.get<FacilitySectorSummary[]>(
      "/api/v1/sensitive-customer-registry/reference-data/facility-sectors",
    ),
  createFacilitySector: (payload: FacilitySectorCreate) =>
    apiClient.post<FacilitySectorSummary>(
      "/api/v1/sensitive-customer-registry/reference-data/facility-sectors",
      payload,
    ),
  updateFacilitySector: (facilitySectorId: number, payload: FacilitySectorUpdate) =>
    apiClient.patch<FacilitySectorSummary>(
      `/api/v1/sensitive-customer-registry/reference-data/facility-sectors/${facilitySectorId}`,
      payload,
    ),
  listSensitivityClassifications: () =>
    apiClient.get<SensitivityClassificationSummary[]>(
      "/api/v1/sensitive-customer-registry/reference-data/sensitivity-classifications",
    ),
  createSensitivityClassification: (payload: SensitivityClassificationCreate) =>
    apiClient.post<SensitivityClassificationSummary>(
      "/api/v1/sensitive-customer-registry/reference-data/sensitivity-classifications",
      payload,
    ),
  updateSensitivityClassification: (
    sensitivityClassificationId: number,
    payload: SensitivityClassificationUpdate,
  ) =>
    apiClient.patch<SensitivityClassificationSummary>(
      `/api/v1/sensitive-customer-registry/reference-data/sensitivity-classifications/${sensitivityClassificationId}`,
      payload,
    ),
};
