import { apiClient } from "../../api/client";
import type {
  EnterInErrorRequest,
  PublicationReviewResult,
  PublishRequest,
  PublishResult,
  UflsDirectAssignmentCreateRequest,
  UflsDirectAssignmentDetail,
  UflsDirectAssignmentMoveRequest,
  UflsPocketAssignmentCreateRequest,
  UflsPocketAssignmentDetail,
  UflsSchemeCreateRequest,
  UflsSchemeDetail,
  UflsSchemeSummary,
  UflsSchemeVersionCreateRequest,
  UflsSchemeVersionDetail,
  UflsSchemeVersionMetadataUpdateRequest,
  UflsSchemeVersionSummary,
  UflsStageCreateRequest,
  UflsStageDetail,
  UflsStageUpdateRequest,
  UflsVersionEngineeringSummary,
} from "./types";

/** Endpoint shapes per backend/app/modules/ufls/router.py. */
export const uflsApi = {
  listSchemes: () => apiClient.get<UflsSchemeSummary[]>("/api/v1/ufls/schemes"),
  createScheme: (payload: UflsSchemeCreateRequest) =>
    apiClient.post<UflsSchemeDetail>("/api/v1/ufls/schemes", payload),
  getScheme: (schemeId: string) =>
    apiClient.get<UflsSchemeDetail>(`/api/v1/ufls/schemes/${schemeId}`),
  listSchemeVersions: (schemeId: string) =>
    apiClient.get<UflsSchemeVersionSummary[]>(`/api/v1/ufls/schemes/${schemeId}/versions`),
  createDraftVersion: (schemeId: string, payload: UflsSchemeVersionCreateRequest) =>
    apiClient.post<UflsSchemeVersionDetail>(
      `/api/v1/ufls/schemes/${schemeId}/versions`,
      payload,
    ),

  getVersion: (versionId: string) =>
    apiClient.get<UflsSchemeVersionDetail>(`/api/v1/ufls/versions/${versionId}`),
  updateVersionMetadata: (versionId: string, payload: UflsSchemeVersionMetadataUpdateRequest) =>
    apiClient.patch<UflsSchemeVersionDetail>(`/api/v1/ufls/versions/${versionId}`, payload),
  deleteDraftVersion: (versionId: string) =>
    apiClient.delete<void>(`/api/v1/ufls/versions/${versionId}`),
  enterInError: (versionId: string, payload: EnterInErrorRequest) =>
    apiClient.post<UflsSchemeVersionDetail>(
      `/api/v1/ufls/versions/${versionId}/enter-in-error`,
      payload,
    ),

  listStages: (versionId: string) =>
    apiClient.get<UflsStageDetail[]>(`/api/v1/ufls/versions/${versionId}/stages`),
  addStage: (versionId: string, payload: UflsStageCreateRequest) =>
    apiClient.post<UflsStageDetail>(`/api/v1/ufls/versions/${versionId}/stages`, payload),
  updateStage: (stageId: string, payload: UflsStageUpdateRequest) =>
    apiClient.patch<UflsStageDetail>(`/api/v1/ufls/stages/${stageId}`, payload),
  removeStage: (stageId: string) => apiClient.delete<void>(`/api/v1/ufls/stages/${stageId}`),

  listDirectAssignments: (stageId: string) =>
    apiClient.get<UflsDirectAssignmentDetail[]>(
      `/api/v1/ufls/stages/${stageId}/direct-assignments`,
    ),
  addDirectAssignment: (stageId: string, payload: UflsDirectAssignmentCreateRequest) =>
    apiClient.post<UflsDirectAssignmentDetail>(
      `/api/v1/ufls/stages/${stageId}/direct-assignments`,
      payload,
    ),
  moveDirectAssignment: (assignmentId: string, payload: UflsDirectAssignmentMoveRequest) =>
    apiClient.patch<UflsDirectAssignmentDetail>(
      `/api/v1/ufls/direct-assignments/${assignmentId}/move`,
      payload,
    ),
  removeDirectAssignment: (assignmentId: string) =>
    apiClient.delete<void>(`/api/v1/ufls/direct-assignments/${assignmentId}`),

  listPocketAssignments: (stageId: string) =>
    apiClient.get<UflsPocketAssignmentDetail[]>(
      `/api/v1/ufls/stages/${stageId}/pocket-assignments`,
    ),
  addPocketAssignment: (stageId: string, payload: UflsPocketAssignmentCreateRequest) =>
    apiClient.post<UflsPocketAssignmentDetail>(
      `/api/v1/ufls/stages/${stageId}/pocket-assignments`,
      payload,
    ),
  removePocketAssignment: (assignmentId: string) =>
    apiClient.delete<void>(`/api/v1/ufls/pocket-assignments/${assignmentId}`),

  getEngineeringSummary: (versionId: string) =>
    apiClient.get<UflsVersionEngineeringSummary>(`/api/v1/ufls/versions/${versionId}/summary`),
  getPublicationReview: (versionId: string) =>
    apiClient.get<PublicationReviewResult>(
      `/api/v1/ufls/versions/${versionId}/publication-review`,
    ),
  publish: (versionId: string, payload: PublishRequest) =>
    apiClient.post<PublishResult>(`/api/v1/ufls/versions/${versionId}/publish`, payload),
};
