/**
 * Mirrors backend/app/modules/ufls/schemas.py. The frontend performs no
 * authoritative engineering logic (CLAUDE.md A12) — these types exist
 * only to describe the API contract the backend already enforces.
 */

import type {
  SchemeVersionLifecycleStatus,
  UserSummaryLike,
} from "../../components/scheme-platform/types";

export interface UflsSchemeCreateRequest {
  name: string;
  description?: string | null;
}

export interface UflsSchemeSummary {
  ufls_scheme_id: string;
  name: string;
  description: string | null;
  published_version_number: number | null;
  latest_draft_version_number: number | null;
}

export interface UflsSchemeDetail {
  ufls_scheme_id: string;
  name: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface UflsSchemeVersionCreateRequest {
  copied_from_version_id?: string | null;
}

export interface UflsSchemeVersionMetadataUpdateRequest {
  stage_setting_set_id?: string | null;
  study_reference?: string | null;
  effective_date?: string | null;
  topology_version_id?: string | null;
  load_snapshot_id?: string | null;
  engineering_remarks?: string | null;
}

export interface UflsSchemeVersionSummary {
  version_id: string;
  scheme_id: string;
  ufls_scheme_id: string;
  version_number: number;
  lifecycle_status: SchemeVersionLifecycleStatus;
  published_at: string | null;
  engineering_remarks: string | null;
}

export interface UflsSchemeVersionDetail {
  version_id: string;
  scheme_id: string;
  ufls_scheme_id: string;
  version_number: number;
  lifecycle_status: SchemeVersionLifecycleStatus;
  published_at: string | null;
  published_by: UserSummaryLike | null;
  superseded_at: string | null;
  entered_in_error_at: string | null;
  entered_in_error_by: UserSummaryLike | null;
  entered_in_error_reason: string | null;
  engineering_remarks: string | null;
  created_at: string;
  updated_at: string;
  stage_setting_set_id: string | null;
  study_reference: string | null;
  effective_date: string | null;
  topology_version_id: string | null;
  load_snapshot_id: string | null;
}

export interface EnterInErrorRequest {
  reason: string;
}

export interface UflsStageCreateRequest {
  stage_setting_id: string;
  target_mw?: string | null;
  engineering_remarks?: string | null;
}

export interface UflsStageUpdateRequest {
  target_mw?: string | null;
  engineering_remarks?: string | null;
}

/**
 * One independent frequency-time operating criterion for a UFLS stage
 * (Stage Setting Registry's own `StageSettingTrigger` — ADR-025).
 */
export interface UflsStageTriggerSummary {
  stage_setting_trigger_id: string;
  trigger_order: number;
  threshold_value: number;
  threshold_unit: string;
  time_delay_ms: number;
}

export interface UflsStageDetail {
  ufls_stage_id: string;
  scheme_version_id: string;
  stage_setting_id: string;
  stage_order: number;
  triggers: UflsStageTriggerSummary[];
  target_mw: string | null;
  engineering_remarks: string | null;
  direct_assignment_count: number;
  pocket_assignment_count: number;
}

export interface UflsDirectAssignmentCreateRequest {
  transformer_terminal_id: string;
  remarks?: string | null;
}

export interface UflsDirectAssignmentMoveRequest {
  target_ufls_stage_id: string;
}

export interface UflsDirectAssignmentDetail {
  ufls_direct_assignment_id: string;
  ufls_stage_id: string;
  transformer_terminal_id: string;
  substation_id: string;
  substation_mnemonic: string;
  remarks: string | null;
  created_at: string;
}

export interface UflsPocketAssignmentCreateRequest {
  circuit_terminal_ids: string[];
  remarks?: string | null;
}

export interface UflsPocketAssignmentDetail {
  ufls_pocket_assignment_id: string;
  ufls_stage_id: string;
  circuit_terminal_ids: string[];
  remarks: string | null;
  created_at: string;
}

export interface UflsStageMwSummary {
  ufls_stage_id: string;
  stage_order: number;
  target_mw: string | null;
  direct_assignment_count: number;
  pocket_assignment_count: number;
}

export interface UflsVersionEngineeringSummary {
  scheme_version_id: string;
  total_target_mw: string;
  stage_summaries: UflsStageMwSummary[];
  direct_assignment_count: number;
  pocket_assignment_count: number;
  distinct_substation_count: number;
  unresolved_finding_count: number;
  sensitive_customer_finding_count: number;
  alsf_finding_count: number;
}

export interface PublicationPrerequisiteSummary {
  prerequisite_code: string;
  passed: boolean;
  description: string;
  affected_object_type: string | null;
  affected_object_id: string | null;
}

export interface FindingLike {
  finding_type: string;
  severity: string;
  source: string;
  description: string;
  affected_object_type: string | null;
  affected_object_id: string | null;
  evidence: Record<string, unknown> | null;
}

export interface PublicationReviewResult {
  scheme_version_id: string;
  prerequisites: PublicationPrerequisiteSummary[];
  all_prerequisites_passed: boolean;
  findings: FindingLike[];
}

export interface PublishAcknowledgementInput {
  finding_index: number;
  justification: string;
}

export interface PublishRequest {
  publication_event_id: string;
  acknowledgements: PublishAcknowledgementInput[];
  remarks?: string | null;
}

export interface PublishResult {
  publication_record_id: string;
  scheme_version_id: string;
  published_at: string;
  finding_count: number;
  acknowledgement_count: number;
}
