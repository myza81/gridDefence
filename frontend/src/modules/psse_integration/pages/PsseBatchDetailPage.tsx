import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { psseIntegrationApi } from "../api";
import type { BatchStatus, FindingGroup, ImportType, VersionStatus } from "../types";

const ACTIVATABLE_STATUSES = new Set(["Completed", "CompletedWithWarnings"]);

function formatImportType(importType: ImportType): string {
  return importType === "FULL_TOPOLOGY_WITH_LOAD"
    ? "Full Network Topology + Load Snapshot"
    : "Load Snapshot Only";
}

function formatStatusHeadline(status: BatchStatus): { headline: string; subtext: string } {
  if (status === "Failed") {
    return { headline: "Import Failed", subtext: "This import did not complete." };
  }
  if (status === "CompletedWithWarnings") {
    return { headline: "Import Completed", subtext: "Engineering review recommended." };
  }
  return { headline: "Import Completed", subtext: "This snapshot is ready for engineering review." };
}

const GROUP_HEADINGS: Record<string, string> = {
  engineering_review_required: "Engineering Review Required",
  parser_notices: "Parser Notices",
  informational: "Informational",
};
const GROUP_ORDER = ["engineering_review_required", "parser_notices", "informational"];

/** One import batch's detail — the Import Result page (Phase 6.1
 * engineering presentation refinement, §8.9d) an engineer reviews to
 * answer: did the import succeed, is the operational context usable, what
 * needs engineering attention, and can I confidently continue with scheme
 * review. Organized around those four questions, not around `BatchSummary`'s
 * own field order — same principle as the Preview page's own refinement
 * (§8.9b), applied here to Commit's result. */
export function PsseBatchDetailPage() {
  const { batchId } = useParams<{ batchId: string }>();
  const { permissions } = useAuth();
  const canActivate = permissions.has("psse_integration.activate");
  const queryClient = useQueryClient();

  const batchQuery = useQuery({
    queryKey: ["psse-integration", "batch", batchId],
    queryFn: () => psseIntegrationApi.getBatch(batchId as string),
    enabled: batchId !== undefined,
  });
  const batch = batchQuery.data;

  // The one signal that tells us whether this batch's own result has
  // actually been promoted to Current — a batch never knows this about
  // itself (Activation is a later, separate, optional action, §8.10);
  // the referenced LoadSnapshot's own status is the authoritative answer,
  // for both import types (every successful commit creates one).
  const loadSnapshotQuery = useQuery({
    queryKey: ["psse-integration", "load-snapshot", batch?.load_snapshot_id],
    queryFn: () => psseIntegrationApi.getLoadSnapshot(batch?.load_snapshot_id as string),
    enabled: batch?.load_snapshot_id !== null && batch?.load_snapshot_id !== undefined,
  });
  const activationStatus: VersionStatus | null = loadSnapshotQuery.data?.status ?? null;

  const [changeReason, setChangeReason] = useState("");
  const [activateError, setActivateError] = useState<string | null>(null);

  const activateMutation = useMutation({
    mutationFn: () =>
      psseIntegrationApi.activateBatch(batchId as string, { change_reason: changeReason }),
    onSuccess: () => {
      setActivateError(null);
      setChangeReason("");
      void queryClient.invalidateQueries({ queryKey: ["psse-integration", "batch", batchId] });
      void queryClient.invalidateQueries({ queryKey: ["psse-integration", "current-status"] });
      void queryClient.invalidateQueries({
        queryKey: ["psse-integration", "load-snapshot", batch?.load_snapshot_id],
      });
    },
    onError: (err: unknown) =>
      setActivateError(err instanceof ApiError ? err.message : "Activation failed."),
  });

  function handleActivateSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    activateMutation.mutate();
  }

  if (batchQuery.isLoading) {
    return <p>Loading batch...</p>;
  }
  if (batchQuery.isError || !batch) {
    return <p role="alert">Import batch not found.</p>;
  }

  const isActivatable = ACTIVATABLE_STATUSES.has(batch.status);
  const { headline, subtext } = formatStatusHeadline(batch.status);
  const hasFindings = batch.finding_groups.length > 0;
  const groupsByBucket = new Map<string, FindingGroup[]>();
  for (const group of batch.finding_groups) {
    const existing = groupsByBucket.get(group.group) ?? [];
    existing.push(group);
    groupsByBucket.set(group.group, existing);
  }

  return (
    <section>
      <h2>Import batch: {batch.source_file_reference}</h2>

      {/* --- 1. Import Summary — did the import succeed? -------------------- */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h3>{headline}</h3>
        <p>{subtext}</p>
        {batch.fatal_error && <p role="alert">{batch.fatal_error}</p>}
        {batch.status !== "Failed" && (
          <ul>
            <li>
              ✓{" "}
              {batch.import_type === "FULL_TOPOLOGY_WITH_LOAD"
                ? "Network topology imported"
                : "Network topology referenced (existing, unchanged)"}
            </li>
            {batch.load_snapshot_id && <li>✓ Load snapshot imported</li>}
            {batch.load_snapshot_id && <li>✓ Operational context imported</li>}
          </ul>
        )}
        <dl>
          <dt>Snapshot Type</dt>
          <dd>{formatImportType(batch.import_type)}</dd>
          <dt>Imported by</dt>
          <dd>{batch.imported_by.username}</dd>
          <dt>Imported on</dt>
          <dd>{batch.created_at}</dd>
        </dl>
      </div>

      {/* --- 2. Import Health — where am I in the workflow? ------------------ */}
      {batch.status !== "Failed" && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h3>Import Health</h3>
          <dl>
            <dt>Parsing</dt>
            <dd>Completed</dd>
            <dt>Operational Context</dt>
            <dd>{batch.load_snapshot_id ? "Imported" : "Not Imported"}</dd>
            <dt>Current Topology</dt>
            <dd>
              {activationStatus === "Current"
                ? "Current (Activated)"
                : activationStatus === "Superseded"
                  ? "Superseded (previously Current)"
                  : "Pending Activation"}
            </dd>
            <dt>Engineering Review</dt>
            <dd>{hasFindings ? "Recommended" : "Not Required"}</dd>
            <dt>Activation</dt>
            <dd>
              {activationStatus === "Current"
                ? "Activated"
                : activationStatus === "Superseded"
                  ? "Previously Activated (Superseded)"
                  : "Not Yet Performed"}
            </dd>
          </dl>
        </div>
      )}

      {/* --- 3. Registry Matching — does GridDefence understand it? --------- */}
      {batch.status !== "Failed" && (
        <div style={{ marginBottom: "1.5rem" }}>
          <h3>Registry Matching</h3>
          {batch.matched_count === null || batch.unmatched_count === null ? (
            <p>No registry matching data is available for this import.</p>
          ) : (
            <dl>
              <dt>
                {batch.import_type === "LOAD_ONLY"
                  ? "Load Buses Matched Against Current Topology"
                  : "Registered Substations Matched"}
              </dt>
              <dd>{batch.matched_count}</dd>
              <dt>{batch.import_type === "LOAD_ONLY" ? "Unmatched Load Buses" : "Unmatched Buses"}</dt>
              <dd>{batch.unmatched_count}</dd>
              <dt>Matching Coverage</dt>
              <dd>{batch.coverage_percent}%</dd>
            </dl>
          )}
        </div>
      )}

      {/* --- 4 & 5. Engineering Findings + Detailed Findings ------------------ */}
      <div style={{ marginBottom: "1.5rem" }}>
        <h3>Engineering Findings</h3>
        {!hasFindings && <p>No engineering findings detected.</p>}
        {GROUP_ORDER.filter((bucket) => groupsByBucket.has(bucket)).map((bucket) => (
          <div key={bucket} style={{ marginBottom: "1rem" }}>
            <h4>{GROUP_HEADINGS[bucket]}</h4>
            {(groupsByBucket.get(bucket) ?? []).map((group) => (
              <div key={group.category}>
                <p>{group.summary}</p>
                <details>
                  <summary>Show details ({group.count})</summary>
                  <ul>
                    {group.details.map((detail, index) => (
                      <li key={index}>{detail}</li>
                    ))}
                  </ul>
                </details>
              </div>
            ))}
          </div>
        ))}
      </div>

      {canActivate && isActivatable && (
        <>
          <h3>Activate</h3>
          <p>
            Activating this import promotes the imported Network Topology and Load Snapshot to
            become the Current Operational Context that GridDefence uses. The previously Current
            Operational Context is superseded, not deleted — it remains permanently in the
            engineering audit history. This action is explicit, privileged, and fully audited.
          </p>
          <form onSubmit={handleActivateSubmit}>
            <label htmlFor="activate-change-reason">Reason for Activation</label>
            <br />
            <input
              id="activate-change-reason"
              value={changeReason}
              onChange={(e) => setChangeReason(e.target.value)}
              required
            />
            <p style={{ fontSize: "0.875rem", color: "#555", margin: "0.25rem 0 0.75rem" }}>
              This information will be recorded in the engineering audit log.
            </p>
            <button type="submit" disabled={activateMutation.isPending}>
              Activate
            </button>
            {activateError && <p role="alert">{activateError}</p>}
            {activateMutation.isSuccess && (
              <div role="status">
                <p>
                  <strong>Operational Context successfully activated.</strong>
                </p>
                <p>
                  The imported Network Topology and Load Snapshot are now the Current Operational
                  Context used by GridDefence.
                </p>
              </div>
            )}
          </form>
        </>
      )}

      {!isActivatable && batch.status !== "Failed" && (
        <p>A batch with status &quot;{batch.status}&quot; cannot be activated.</p>
      )}

      {/* --- Advanced Information — implementation detail, collapsed --------- */}
      <details style={{ marginTop: "1.5rem" }}>
        <summary>Advanced Information</summary>
        <dl>
          <dt>Structural Signature (technical, for support/debugging use)</dt>
          <dd>{batch.computed_signature ?? "Not applicable (load-only snapshot)"}</dd>
          <dt>Topology version</dt>
          <dd>
            {batch.topology_version_id ? (
              <Link to={`/psse-integration/topology-versions/${batch.topology_version_id}`}>
                {batch.topology_version_id}
              </Link>
            ) : (
              "—"
            )}
          </dd>
        </dl>
      </details>
    </section>
  );
}
