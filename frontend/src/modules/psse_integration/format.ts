import type { BusClassification, CorrelationStatus, ImportType } from "./types";

/** Shared between the Preview page and the Operational Context Inspector's
 * Overview tab — a single formatting rule, not duplicated. */
export function formatSnapshotType(importType: ImportType): string {
  return importType === "FULL_TOPOLOGY_WITH_LOAD"
    ? "Full Network Topology + Load Snapshot"
    : "Load Snapshot Only";
}

const BUS_CLASSIFICATION_LABELS: Record<BusClassification, string> = {
  SWITCHYARD_BUS: "Switchyard Bus",
  SPLIT_SWITCHYARD_BUS: "Split Switchyard Bus",
  FICTITIOUS_BUS: "Fictitious Bus",
  BLANK_NAMED_BUS: "Blank-named Bus",
  OTHER_NON_CONFORMING_BUS: "Other Non-conforming Bus",
};

/** Plain-language label for EDR-007 §4's Bus Name classification (Phase
 * 7A) — never the raw enum value, matching this module's existing
 * convention (see `formatSnapshotType`). */
export function formatBusClassification(classification: BusClassification): string {
  return BUS_CLASSIFICATION_LABELS[classification];
}

const CORRELATION_STATUS_LABELS: Record<CorrelationStatus, string> = {
  CORRELATED: "Correlated",
  UNMATCHED_OPERATIONAL: "Unmatched (Operational)",
  UNMATCHED_REGISTRY: "Unmatched (Registry)",
  AMBIGUOUS: "Ambiguous",
  OUTSIDE_CURRENT_SCOPE: "Outside Current Scope",
  ENGINEERING_REVIEW_REQUIRED: "Engineering Review Required",
};

/** Plain-language label for the Correlated Operational Model's shared
 * Correlation Status vocabulary (Phase 7C) — never the raw enum value,
 * matching this module's existing convention. */
export function formatCorrelationStatus(status: CorrelationStatus): string {
  return CORRELATION_STATUS_LABELS[status];
}
