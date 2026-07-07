import { useMutation } from "@tanstack/react-query";
import type { ChangeEvent } from "react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { psseIntegrationApi } from "../api";
import { formatSnapshotType } from "../format";
import type { BatchSummary, CommitSubmission, PreviewResult } from "../types";
import { useJobPolling } from "../useJobPolling";

/** Discriminates Commit's two possible response shapes (§8.9c) — Direct
 * mode's completed `BatchSummary` always has `batch_id`; Queue mode's
 * `JobSubmitted` never does. */
function isCommitCompleted(response: CommitSubmission): response is BatchSummary {
  return "batch_id" in response;
}

function formatTopologyStatus(result: PreviewResult): string {
  if (result.import_type === "LOAD_ONLY") {
    // A load-only snapshot always references the Current topology
    // (psse-integration-module.md §8.7) — `topology_reused` is always
    // `false` for this import type at the API level, but that reflects "no
    // new topology was introduced," not "this doesn't match anything."
    return "References the currently registered network topology";
  }
  return result.topology_reused
    ? "Matches the currently registered network topology"
    : "Introduces a new network topology";
}

const UNRECOGNIZED_SECTION_PATTERN = "is not recognized by this parser";
const NO_CURRENT_TOPOLOGY_PATTERN = "No Current TopologyVersion exists";

interface ClassifiedFindings {
  requiresAttention: string[];
  informational: string[];
}

/** Pattern-based classification of existing parser/validation message text
 * — the backend does not yet tag findings with a severity, so this infers
 * it from known message shapes rather than inventing new backend state.
 * See the Phase 6 implementation report's observations for a more robust,
 * backend-tagged alternative. */
function classifyFindings(warnings: string[]): ClassifiedFindings {
  const requiresAttention: string[] = [];
  const informational: string[] = [];
  for (const warning of warnings) {
    if (warning.includes(UNRECOGNIZED_SECTION_PATTERN)) {
      informational.push(warning);
    } else {
      requiresAttention.push(warning);
    }
  }
  return { requiresAttention, informational };
}

/** A recommendation only — the engineer still decides whether to commit;
 * nothing here blocks or auto-approves an import (CLAUDE.md A12). */
function importReadinessMessage(result: PreviewResult, findings: ClassifiedFindings): string {
  if (findings.requiresAttention.length > 0) {
    return "Review the findings above before importing.";
  }
  if (result.unmatched_bus_count > 0) {
    return "Review unmatched substations before importing.";
  }
  return "Preview completed successfully — this snapshot appears ready for import.";
}

/** Upload a PSS/E RAW file, preview its parsed content (zero persistence —
 * psse-integration-module.md §8.9), then optionally commit it.
 *
 * The Preview summary is organized around four engineering questions
 * (Phase 6 engineering presentation refinement, §8.9b): what snapshot was
 * uploaded (Snapshot Summary), does GridDefence understand it (Registry
 * Matching), is anything wrong (Engineering Findings), and is it ready to
 * import (Import Readiness) — with implementation detail (the structural
 * signature) collapsed into Advanced Information.
 *
 * Preview executes synchronously, in-request (execution-model refinement,
 * §8.9a) — its result is available directly from the submit response, with
 * no job to poll.
 *
 * Commit's execution mechanism is configurable on the backend (Phase 6 —
 * Execution Engine, §8.9c): Direct mode (default) completes immediately,
 * exactly like Preview; Queue mode (Redis+RQ) returns a job to poll,
 * unchanged from before this refactor. This page does not know or choose
 * which mode is active — it reacts to whichever response shape it
 * receives (`isCommitCompleted`), so there is never unnecessary polling
 * when the backend already completed the work. */
export function PsseImportUploadPage() {
  const { permissions } = useAuth();
  const canImport = permissions.has("psse_integration.import");
  const navigate = useNavigate();

  const [file, setFile] = useState<File | null>(null);
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [directCommitResult, setDirectCommitResult] = useState<BatchSummary | null>(null);
  const [commitJobId, setCommitJobId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const commitJob = useJobPolling(commitJobId);

  const submitPreviewMutation = useMutation({
    mutationFn: () => psseIntegrationApi.submitPreview(file as File),
    onSuccess: (result) => {
      setError(null);
      setCommitJobId(null);
      setPreviewResult(result);
    },
    onError: (err: unknown) => {
      setPreviewResult(null);
      setError(err instanceof ApiError ? err.message : "Failed to preview file.");
    },
  });

  const submitCommitMutation = useMutation({
    mutationFn: () => psseIntegrationApi.submitCommit(file as File),
    onSuccess: (response) => {
      setError(null);
      if (isCommitCompleted(response)) {
        setCommitJobId(null);
        setDirectCommitResult(response);
      } else {
        setDirectCommitResult(null);
        setCommitJobId(response.job_id);
      }
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Failed to submit commit."),
  });

  function handleFileChange(event: ChangeEvent<HTMLInputElement>): void {
    setFile(event.target.files?.[0] ?? null);
    setPreviewResult(null);
    setDirectCommitResult(null);
    setCommitJobId(null);
    setError(null);
  }

  const commitResult =
    directCommitResult ??
    (commitJob.data?.status === "finished" ? (commitJob.data.result as BatchSummary) : null);
  const commitFailed = commitJob.data?.status === "failed";

  if (!canImport) {
    return <p role="alert">You do not have permission to import PSS/E files.</p>;
  }

  const findings = previewResult ? classifyFindings(previewResult.warnings) : null;
  const noCurrentTopology =
    previewResult?.import_type === "LOAD_ONLY" &&
    previewResult.warnings.some((warning) => warning.includes(NO_CURRENT_TOPOLOGY_PATTERN));

  return (
    <section>
      <h2>Import PSS/E RAW file</h2>
      <p>
        Supports both a full topology + load/generation snapshot and a load-only snapshot
        (psse-integration-module.md §8). The import type is detected automatically from the
        file's own content.
      </p>

      <div>
        <label htmlFor="raw-file-input">RAW file</label>
        <br />
        <input id="raw-file-input" type="file" accept=".raw" onChange={handleFileChange} />
      </div>

      <div style={{ marginTop: "1rem" }}>
        <button
          type="button"
          disabled={!file || submitPreviewMutation.isPending}
          onClick={() => submitPreviewMutation.mutate()}
        >
          Preview
        </button>
      </div>

      {error && <p role="alert">{error}</p>}

      {submitPreviewMutation.isPending && <p>Parsing and validating file...</p>}

      {previewResult && findings && (
        <div style={{ marginTop: "1rem", border: "1px solid #ccc", padding: "1rem" }}>
          <div style={{ marginBottom: "1rem" }}>
            <button
              type="button"
              onClick={() =>
                navigate("/psse-integration/import/inspect", { state: { previewResult } })
              }
            >
              Inspect Imported Data
            </button>
          </div>

          <h3>Snapshot Summary</h3>
          <dl>
            <dt>Snapshot Type</dt>
            <dd>{formatSnapshotType(previewResult.import_type)}</dd>
            <dt>PSS/E RAW Version</dt>
            <dd>{previewResult.raw_version ?? "Not available"}</dd>
            <dt>Network Topology Status</dt>
            <dd>{formatTopologyStatus(previewResult)}</dd>
          </dl>
          <h4>Network Size</h4>
          <dl>
            <dt>Buses</dt>
            <dd>{previewResult.bus_count}</dd>
            <dt>Transmission Lines (Branches)</dt>
            <dd>{previewResult.branch_count}</dd>
            <dt>Transformers</dt>
            <dd>{previewResult.transformer_count}</dd>
            <dt>Loads</dt>
            <dd>{previewResult.load_count}</dd>
            <dt>Generators</dt>
            <dd>{previewResult.generator_count}</dd>
          </dl>

          <h3>Registry Matching</h3>
          {noCurrentTopology ? (
            <p>No current network topology exists yet — load buses could not be validated.</p>
          ) : (
            <dl>
              <dt>
                {previewResult.import_type === "LOAD_ONLY"
                  ? "Load Buses Matched Against Current Topology"
                  : "Registered Substations Matched"}
              </dt>
              <dd>{previewResult.matched_bus_count}</dd>
              <dt>
                {previewResult.import_type === "LOAD_ONLY"
                  ? "Unmatched Load Buses"
                  : "Unrecognized Buses"}
              </dt>
              <dd>{previewResult.unmatched_bus_count}</dd>
              <dt>
                {previewResult.import_type === "LOAD_ONLY"
                  ? "Load Match Coverage"
                  : "Substation Match Coverage"}
              </dt>
              <dd>{previewResult.coverage_percent}%</dd>
            </dl>
          )}

          <h3>Engineering Findings</h3>
          {findings.requiresAttention.length === 0 && findings.informational.length === 0 && (
            <p>No engineering findings detected.</p>
          )}
          {findings.requiresAttention.length > 0 && (
            <>
              <h4>Requires Attention</h4>
              <ul>
                {findings.requiresAttention.map((finding, index) => (
                  <li key={index}>{finding}</li>
                ))}
              </ul>
            </>
          )}
          {findings.informational.length > 0 && (
            <>
              <h4>Informational</h4>
              <ul>
                {findings.informational.map((finding, index) => (
                  <li key={index}>{finding}</li>
                ))}
              </ul>
            </>
          )}

          <h3>Import Readiness</h3>
          <p>{importReadinessMessage(previewResult, findings)}</p>

          <details style={{ marginTop: "1rem" }}>
            <summary>Advanced Information</summary>
            <dl>
              <dt>Structural Signature (technical, for support/debugging use)</dt>
              <dd>{previewResult.computed_signature ?? "Not applicable (load-only snapshot)"}</dd>
            </dl>
          </details>

          <div style={{ marginTop: "1rem" }}>
            <button
              type="button"
              disabled={submitCommitMutation.isPending || commitJob.data?.status === "started"}
              onClick={() => submitCommitMutation.mutate()}
            >
              Commit
            </button>
          </div>
        </div>
      )}

      {(submitCommitMutation.isPending || (commitJobId && !commitResult && !commitFailed)) && (
        <p>Committing import...</p>
      )}
      {commitFailed && <p role="alert">Commit failed: {commitJob.data?.error}</p>}

      {commitResult && (
        <div style={{ marginTop: "1rem", border: "1px solid #ccc", padding: "1rem" }}>
          <h3>Import committed</h3>
          <p>
            Batch status: <strong>{commitResult.status}</strong>
          </p>
          <p>
            Committing persists the imported data but does not make it Current — an
            administrator must explicitly{" "}
            <Link to={`/psse-integration/batches/${commitResult.batch_id}`}>
              review and activate this batch
            </Link>
            .
          </p>
        </div>
      )}
    </section>
  );
}
