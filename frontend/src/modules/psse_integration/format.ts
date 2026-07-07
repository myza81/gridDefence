import type { ImportType } from "./types";

/** Shared between the Preview page and the Operational Context Inspector's
 * Overview tab — a single formatting rule, not duplicated. */
export function formatSnapshotType(importType: ImportType): string {
  return importType === "FULL_TOPOLOGY_WITH_LOAD"
    ? "Full Network Topology + Load Snapshot"
    : "Load Snapshot Only";
}
