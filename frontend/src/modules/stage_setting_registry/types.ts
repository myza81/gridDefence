/**
 * Mirrors backend/app/modules/stage_setting_registry/schemas.py. The
 * frontend performs no authoritative engineering logic (CLAUDE.md A12) —
 * these types exist only to describe the API contract the backend already
 * enforces. See docs/architecture/stage-setting-set-architecture.md
 * (ADR-016, ADR-020).
 *
 * Applies to UFLS and UVLS only — EMLS has no Stage Setting Set
 * (stage-setting-set-architecture.md §2).
 */

export type SchemeType = "UFLS" | "UVLS";
export type StageSettingSetStatus = "DRAFT" | "PUBLISHED" | "ENTERED_IN_ERROR";

export interface UserSummary {
  user_id: string;
  username: string;
  display_name: string;
  email: string | null;
}

export interface StageSettingSetCreate {
  scheme_type: SchemeType;
  description?: string | null;
}

export interface StageSettingSetUpdate {
  description?: string | null;
  change_reason?: string | null;
}

export interface StageSettingSetEnterInErrorRequest {
  change_reason: string;
}

/**
 * Creates a stage (`StageSetting`) — identity, order, and (UVLS only)
 * region scope. Carries no threshold or time delay: those belong to the
 * stage's own trigger(s), added separately once the stage exists
 * (ADR-025).
 */
export interface StageSettingCreate {
  stage_order: number;
  region_scope_id?: number | null;
  change_reason?: string | null;
}

export interface StageSettingUpdate {
  region_scope_id?: number | null;
  change_reason?: string | null;
}

export interface StageSettingReorderRequest {
  region_scope_id?: number | null;
  ordered_stage_setting_ids: string[];
  change_reason?: string | null;
}

/** One independent frequency/voltage-time operating criterion for a stage
 * (ADR-025). Satisfaction of any one trigger under a stage constitutes
 * operation of that same stage — multiple triggers are not multiple
 * stages. */
export interface StageSettingTriggerCreate {
  trigger_order: number;
  threshold_value: number;
  time_delay_ms: number;
  change_reason?: string | null;
}

export interface StageSettingTriggerUpdate {
  threshold_value?: number | null;
  time_delay_ms?: number | null;
  change_reason?: string | null;
}

export interface StageSettingTriggerReorderRequest {
  ordered_trigger_ids: string[];
  change_reason?: string | null;
}

export interface StageSettingTriggerDetail {
  stage_setting_trigger_id: string;
  stage_setting_id: string;
  trigger_order: number;
  threshold_value: number;
  threshold_unit: string;
  time_delay_ms: number;
}

export interface StageSettingDetail {
  stage_setting_id: string;
  stage_setting_set_id: string;
  stage_order: number;
  region_scope_id: number | null;
  triggers: StageSettingTriggerDetail[];
}

export interface StageSettingSetSummary {
  stage_setting_set_id: string;
  scheme_type: SchemeType;
  description: string | null;
  status: StageSettingSetStatus;
  setting_count: number;
  updated_at: string;
}

export interface StageSettingSetPage {
  items: StageSettingSetSummary[];
  page: number;
  page_size: number;
  total: number;
}

export interface StageSettingSetDetail {
  stage_setting_set_id: string;
  scheme_type: SchemeType;
  description: string | null;
  status: StageSettingSetStatus;
  settings: StageSettingDetail[];
  created_at: string;
  updated_at: string;
  created_by: UserSummary | null;
  updated_by: UserSummary | null;
}

export interface StageSettingRegistryAuditLogEntry {
  log_id: number;
  subject_type: "STAGE_SETTING_SET" | "STAGE_SETTING" | "STAGE_SETTING_TRIGGER";
  stage_setting_set_id: string | null;
  stage_setting_id: string | null;
  stage_setting_trigger_id: string | null;
  action: string;
  old_value: string | null;
  new_value: string | null;
  changed_at: string;
  changed_by: UserSummary | null;
  change_reason: string | null;
}

export interface StageSettingRegistryAuditLogPage {
  items: StageSettingRegistryAuditLogEntry[];
  page: number;
  page_size: number;
  total: number;
}
