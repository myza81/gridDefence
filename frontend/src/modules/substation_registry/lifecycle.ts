/**
 * Substation lifecycle presentation — a typed MIRROR of the authoritative
 * backend rules, for display only.
 *
 * The engineering rules live in the backend service layer and ADR-014
 * (backend/app/modules/substation_registry/service.py `_STATUS_TRANSITIONS`).
 * The backend remains the sole authority and re-validates every change. This
 * module exists so the UI can *reflect* those rules (badge tone; offering only
 * the legal next states) rather than presenting an illegal action and relying
 * on rejection (Lifecycle visibility §8; Edit/Lifecycle §11–§12). It introduces
 * NO new state and NO new rule — if ADR-014 changes, this table and the service
 * allow-list must change together.
 *
 * The four Substation lifecycle states (ADR-014). Other `operational_status`
 * reference rows (PLANNED/MOTHBALLED/RETIRED) belong to Equipment Registry and
 * are never valid for a Substation — they map to a neutral tone and offer no
 * transitions here.
 */
import type { BadgeTone } from "../../components/ui/Badge";
import type { OperationalStatusSummary } from "../../reference_data/types";

export type SubstationStatusCode = "UNDER_CONSTRUCTION" | "ACTIVE" | "DECOMMISSIONED" | "ENTERED_IN_ERROR";

export const SUBSTATION_STATUS_CODES: SubstationStatusCode[] = [
  "UNDER_CONSTRUCTION",
  "ACTIVE",
  "DECOMMISSIONED",
  "ENTERED_IN_ERROR",
];

/** A newly registered Substation may only start here (service `_ALLOWED_INITIAL_STATUS_CODES`). */
export const INITIAL_STATUS_CODES: SubstationStatusCode[] = ["UNDER_CONSTRUCTION", "ACTIVE"];

/** Closed allow-list of legal transitions, keyed by current code (service `_STATUS_TRANSITIONS`). */
export const STATUS_TRANSITIONS: Record<SubstationStatusCode, SubstationStatusCode[]> = {
  UNDER_CONSTRUCTION: ["ACTIVE", "ENTERED_IN_ERROR"],
  ACTIVE: ["DECOMMISSIONED", "ENTERED_IN_ERROR"],
  DECOMMISSIONED: [],
  ENTERED_IN_ERROR: [],
};

const TONES: Record<SubstationStatusCode, BadgeTone> = {
  UNDER_CONSTRUCTION: "info",
  ACTIVE: "success",
  DECOMMISSIONED: "neutral",
  ENTERED_IN_ERROR: "danger",
};

/** Badge tone for any operational-status code (legacy/foreign codes → neutral). */
export function toneForStatusCode(code: string | undefined): BadgeTone {
  return code && code in TONES ? TONES[code as SubstationStatusCode] : "neutral";
}

/** Only the operational statuses that are valid Substation lifecycle states. */
export function substationStatuses(all: OperationalStatusSummary[]): OperationalStatusSummary[] {
  return all.filter((status) => (SUBSTATION_STATUS_CODES as string[]).includes(status.code));
}

/** Valid initial statuses offered at creation (Under Construction / Active). */
export function initialStatuses(all: OperationalStatusSummary[]): OperationalStatusSummary[] {
  return all.filter((status) => (INITIAL_STATUS_CODES as string[]).includes(status.code));
}

/**
 * The statuses a substation currently in `currentStatusId` may legally move to.
 * Empty when the current state is terminal (Decommissioned / Entered in Error)
 * or a non-substation legacy state — in which case the UI offers no transition.
 */
export function allowedTargetStatuses(
  currentStatusId: number,
  all: OperationalStatusSummary[],
): OperationalStatusSummary[] {
  const current = all.find((status) => status.operational_status_id === currentStatusId);
  const currentCode = current?.code as SubstationStatusCode | undefined;
  const targets = currentCode && currentCode in STATUS_TRANSITIONS ? STATUS_TRANSITIONS[currentCode] : [];
  return all.filter((status) => (targets as string[]).includes(status.code));
}
