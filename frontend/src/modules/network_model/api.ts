import { apiClient } from "../../api/client";
import type {
  ElectricalNeighbour,
  NetworkOverview,
  SubstationConnectivity,
  SubstationEquipment,
  TraversalRequest,
  TraversalResult,
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
};
