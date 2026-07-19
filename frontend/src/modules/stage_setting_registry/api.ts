import { apiClient } from "../../api/client";
import type {
  SchemeType,
  StageSettingCreate,
  StageSettingDetail,
  StageSettingRegistryAuditLogPage,
  StageSettingReorderRequest,
  StageSettingSetCreate,
  StageSettingSetDetail,
  StageSettingSetEnterInErrorRequest,
  StageSettingSetPage,
  StageSettingSetStatus,
  StageSettingSetUpdate,
  StageSettingTriggerCreate,
  StageSettingTriggerDetail,
  StageSettingTriggerReorderRequest,
  StageSettingTriggerUpdate,
  StageSettingUpdate,
} from "./types";

export interface StageSettingSetListFilters {
  page?: number;
  page_size?: number;
  scheme_type?: SchemeType;
  status_filter?: StageSettingSetStatus;
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

/** Endpoint shapes per backend/app/modules/stage_setting_registry/router.py. */
export const stageSettingRegistryApi = {
  list: (filters: StageSettingSetListFilters = {}) =>
    apiClient.get<StageSettingSetPage>(`/api/v1/stage-setting-sets${buildQuery(filters)}`),
  create: (payload: StageSettingSetCreate) =>
    apiClient.post<StageSettingSetDetail>("/api/v1/stage-setting-sets", payload),
  get: (stageSettingSetId: string) =>
    apiClient.get<StageSettingSetDetail>(`/api/v1/stage-setting-sets/${stageSettingSetId}`),
  update: (stageSettingSetId: string, payload: StageSettingSetUpdate) =>
    apiClient.patch<StageSettingSetDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}`,
      payload,
    ),
  deleteDraft: (stageSettingSetId: string) =>
    apiClient.delete<void>(`/api/v1/stage-setting-sets/${stageSettingSetId}`),

  listSettings: (stageSettingSetId: string) =>
    apiClient.get<StageSettingDetail[]>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings`,
    ),
  addSetting: (stageSettingSetId: string, payload: StageSettingCreate) =>
    apiClient.post<StageSettingDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings`,
      payload,
    ),
  reorderSettings: (stageSettingSetId: string, payload: StageSettingReorderRequest) =>
    apiClient.post<StageSettingDetail[]>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/reorder`,
      payload,
    ),
  updateSetting: (
    stageSettingSetId: string,
    stageSettingId: string,
    payload: StageSettingUpdate,
  ) =>
    apiClient.patch<StageSettingDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}`,
      payload,
    ),
  removeSetting: (stageSettingSetId: string, stageSettingId: string) =>
    apiClient.delete<void>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}`,
    ),

  listTriggers: (stageSettingSetId: string, stageSettingId: string) =>
    apiClient.get<StageSettingTriggerDetail[]>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}/triggers`,
    ),
  addTrigger: (
    stageSettingSetId: string,
    stageSettingId: string,
    payload: StageSettingTriggerCreate,
  ) =>
    apiClient.post<StageSettingTriggerDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}/triggers`,
      payload,
    ),
  reorderTriggers: (
    stageSettingSetId: string,
    stageSettingId: string,
    payload: StageSettingTriggerReorderRequest,
  ) =>
    apiClient.post<StageSettingTriggerDetail[]>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}/triggers/reorder`,
      payload,
    ),
  updateTrigger: (
    stageSettingSetId: string,
    stageSettingId: string,
    stageSettingTriggerId: string,
    payload: StageSettingTriggerUpdate,
  ) =>
    apiClient.patch<StageSettingTriggerDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}/triggers/${stageSettingTriggerId}`,
      payload,
    ),
  removeTrigger: (stageSettingSetId: string, stageSettingId: string, stageSettingTriggerId: string) =>
    apiClient.delete<void>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/settings/${stageSettingId}/triggers/${stageSettingTriggerId}`,
    ),

  publish: (stageSettingSetId: string) =>
    apiClient.post<StageSettingSetDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/publish`,
      {},
    ),
  enterInError: (stageSettingSetId: string, payload: StageSettingSetEnterInErrorRequest) =>
    apiClient.post<StageSettingSetDetail>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/enter-in-error`,
      payload,
    ),

  listAuditLog: (stageSettingSetId: string, page = 1, pageSize = 50) =>
    apiClient.get<StageSettingRegistryAuditLogPage>(
      `/api/v1/stage-setting-sets/${stageSettingSetId}/audit-log?page=${page}&page_size=${pageSize}`,
    ),
};
