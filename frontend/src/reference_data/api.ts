import { apiClient } from "../api/client";
import type {
  GridOwnerSummary,
  LineTypeSummary,
  OperationalStatusSummary,
  RegionSummary,
  StateSummary,
  VoltageLevelSummary,
} from "./types";

/** Read-only endpoints — backend/app/reference_data/router.py. */
export const referenceDataApi = {
  listVoltageLevels: () =>
    apiClient.get<VoltageLevelSummary[]>("/api/v1/reference-data/voltage-levels"),
  listRegions: () => apiClient.get<RegionSummary[]>("/api/v1/reference-data/regions"),
  listStates: () => apiClient.get<StateSummary[]>("/api/v1/reference-data/states"),
  listGridOwners: () => apiClient.get<GridOwnerSummary[]>("/api/v1/reference-data/grid-owners"),
  listOperationalStatuses: () =>
    apiClient.get<OperationalStatusSummary[]>("/api/v1/reference-data/operational-statuses"),
  listLineTypes: () => apiClient.get<LineTypeSummary[]>("/api/v1/reference-data/line-types"),
};
