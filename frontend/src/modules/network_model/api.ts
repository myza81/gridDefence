import { apiClient } from "../../api/client";
import type {
  BoundaryPocketEvaluation,
  BoundaryPocketEvaluationRequest,
  ElectricalNeighbour,
  NetworkOverview,
  PathVerificationRequest,
  SnapshotSummary,
  SubstationConnectivity,
  SubstationEquipment,
  TraversalRequest,
  TraversalResult,
  TraversalVerificationResult,
} from "./types";

/** Endpoint shapes per docs/architecture/network-model-module.md §19. */
export const networkModelApi = {
  getOverview: () => apiClient.get<NetworkOverview>("/api/v1/network-model/overview"),
  getSubstationConnectivity: (substationId: string) =>
    apiClient.get<SubstationConnectivity>(
      `/api/v1/network-model/substations/${substationId}/connectivity`,
    ),
  getSubstationEquipment: (substationId: string) =>
    apiClient.get<SubstationEquipment>(
      `/api/v1/network-model/substations/${substationId}/equipment`,
    ),
  getSubstationNeighbours: (substationId: string) =>
    apiClient.get<ElectricalNeighbour[]>(
      `/api/v1/network-model/substations/${substationId}/neighbours`,
    ),
  traverse: (payload: TraversalRequest) =>
    apiClient.post<TraversalResult>("/api/v1/network-model/traverse", payload),
  // Phase 7F — Operational Snapshot Verification Workspace (§19.10).
  getSnapshotSummary: () =>
    apiClient.get<SnapshotSummary>("/api/v1/network-model/verification/snapshot-summary"),
  verifyPath: (payload: PathVerificationRequest) =>
    apiClient.post<TraversalVerificationResult>(
      "/api/v1/network-model/verification/traverse",
      payload,
    ),
  // Foundation Hardening Sprint A — Boundary Pocket foundation
  // (docs/architecture/boundary-pocket-architecture.md §7, §10). Transient,
  // stateless — no persistence endpoint exists or is intended.
  evaluateBoundary: (payload: BoundaryPocketEvaluationRequest) =>
    apiClient.post<BoundaryPocketEvaluation>(
      "/api/v1/network-model/boundary-pocket-evaluations",
      payload,
    ),
};
