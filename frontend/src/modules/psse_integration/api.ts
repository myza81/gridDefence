import { apiClient } from "../../api/client";
import type {
  ActivateRequest,
  BatchPage,
  BatchSummary,
  CircuitCorrelation,
  CommitSubmission,
  CurrentStatus,
  DiscrepancyResolveRequest,
  EquipmentTopologyMapEntry,
  EquipmentTopologyMapPage,
  JobStatus,
  LoadSnapshotPage,
  LoadSnapshotSummary,
  PreviewResult,
  TopologyVersionPage,
  TopologyVersionSummary,
} from "./types";

export interface BatchListFilters {
  page?: number;
  page_size?: number;
  status_filter?: string;
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

/** Endpoint shapes per docs/architecture/psse-integration-module.md §12/§8.9a/§8.9c. */
export const psseIntegrationApi = {
  /** Preview executes synchronously, in-request (§8.9a) — the response
   * body is the `PreviewResult` itself, never a job to poll. */
  submitPreview: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.postForm<PreviewResult>("/api/v1/psse-integration/imports/preview", formData);
  },
  /** Commit's response shape depends on the backend's configured execution
   * mode (§8.9c) — see `CommitSubmission`. The frontend does not choose or
   * need to know which mode is active; it reacts to whichever shape it
   * receives. */
  submitCommit: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiClient.postForm<CommitSubmission>(
      "/api/v1/psse-integration/imports/commit",
      formData,
    );
  },
  getJobStatus: (jobId: string) =>
    apiClient.get<JobStatus>(`/api/v1/psse-integration/imports/jobs/${jobId}`),

  listBatches: (filters: BatchListFilters = {}) =>
    apiClient.get<BatchPage>(`/api/v1/psse-integration/imports/batches${buildQuery(filters)}`),
  getBatch: (batchId: string) =>
    apiClient.get<BatchSummary>(`/api/v1/psse-integration/imports/batches/${batchId}`),
  activateBatch: (batchId: string, payload: ActivateRequest) =>
    apiClient.post<BatchSummary>(
      `/api/v1/psse-integration/imports/batches/${batchId}/activate`,
      payload,
    ),

  listTopologyVersions: (page = 1, pageSize = 50) =>
    apiClient.get<TopologyVersionPage>(
      `/api/v1/psse-integration/topology-versions${buildQuery({ page, page_size: pageSize })}`,
    ),
  getTopologyVersion: (topologyVersionId: string) =>
    apiClient.get<TopologyVersionSummary>(
      `/api/v1/psse-integration/topology-versions/${topologyVersionId}`,
    ),
  recomputeMatching: (topologyVersionId: string) =>
    apiClient.post<{ status: string }>(
      `/api/v1/psse-integration/topology-versions/${topologyVersionId}/recompute-matching`,
    ),

  listLoadSnapshots: (topologyVersionId?: string, page = 1, pageSize = 50) =>
    apiClient.get<LoadSnapshotPage>(
      `/api/v1/psse-integration/load-snapshots${buildQuery({
        topology_version_id: topologyVersionId,
        page,
        page_size: pageSize,
      })}`,
    ),
  getLoadSnapshot: (loadSnapshotId: string) =>
    apiClient.get<LoadSnapshotSummary>(`/api/v1/psse-integration/load-snapshots/${loadSnapshotId}`),

  getCurrentStatus: () => apiClient.get<CurrentStatus>("/api/v1/psse-integration/current-status"),

  listEquipmentMap: (topologyVersionId: string, matchOutcome?: string, page = 1, pageSize = 50) =>
    apiClient.get<EquipmentTopologyMapPage>(
      `/api/v1/psse-integration/topology-versions/${topologyVersionId}/equipment-map${buildQuery({
        match_outcome: matchOutcome,
        page,
        page_size: pageSize,
      })}`,
    ),
  resolveDiscrepancy: (mapId: string, payload: DiscrepancyResolveRequest) =>
    apiClient.post<EquipmentTopologyMapEntry>(
      `/api/v1/psse-integration/equipment-map/${mapId}/resolve`,
      payload,
    ),
  getCircuitCorrelation: (circuitId: string, topologyVersionId: string) =>
    apiClient.get<CircuitCorrelation>(
      `/api/v1/psse-integration/circuits/${circuitId}/correlation${buildQuery({
        topology_version_id: topologyVersionId,
      })}`,
    ),
};
