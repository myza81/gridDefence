/**
 * Shared Defence Scheme Version lifecycle types (ADR-015; EDR-009).
 *
 * Mirrors `backend/app/modules/scheme_platform/lifecycle.py` and
 * `schemas.py` exactly — no `UNDER_REVIEW`/`APPROVED`/`ARCHIVED` state
 * exists under the ratified four-state model. A future concrete scheme
 * module (UFLS, UVLS, EMLS) extends these types with its own
 * scheme-specific fields rather than duplicating the shared ones.
 */

export type SchemeVersionLifecycleStatus =
  | "DRAFT"
  | "PUBLISHED"
  | "SUPERSEDED"
  | "ENTERED_IN_ERROR";

export interface UserSummaryLike {
  displayName: string;
}

/** The shared metadata every concrete scheme version's own detail view
 * includes — a future module composes this alongside its own
 * scheme-specific fields, never duplicating these. */
export interface SchemeVersionLifecycleInfo {
  versionId: string;
  schemeId: string;
  versionNumber: number;
  lifecycleStatus: SchemeVersionLifecycleStatus;

  publishedAt: string | null;
  publishedBy: UserSummaryLike | null;

  supersededAt: string | null;

  enteredInErrorAt: string | null;
  enteredInErrorBy: UserSummaryLike | null;
  enteredInErrorReason: string | null;

  engineeringRemarks: string | null;

  createdAt: string;
  updatedAt: string;
}

/** One historical lifecycle event — the "publication history" this
 * pack's own model actually has (ADR-015 defines no separate
 * review/approval history, since no separate review/approval state
 * exists). Presentation-only shape; the backend already computed which
 * events occurred. */
export interface SchemeVersionLifecycleEvent {
  action: "draft_created" | "published" | "superseded" | "entered_in_error";
  occurredAt: string;
  actor: UserSummaryLike | null;
  reason: string | null;
}
