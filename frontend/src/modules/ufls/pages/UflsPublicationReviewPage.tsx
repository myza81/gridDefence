import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useAuth } from "../../iam/AuthContext";
import { uflsApi } from "../api";

/**
 * UFLS Publication Review (task Frontend Scope §"Publication Review") —
 * blocking prerequisites, warnings/findings, stage and overall totals,
 * missing data, sensitive-customer and defence-capability findings,
 * unresolved references. Passing every automated check here is a
 * structural precondition, never a substitute for engineering approval
 * or judgement (task's own explicit instruction; CLAUDE.md A12) — the
 * Administrator publishing still makes the engineering decision.
 */
export function UflsPublicationReviewPage() {
  const { versionId } = useParams<{ versionId: string }>();
  const navigate = useNavigate();
  const { permissions } = useAuth();
  const canPublish = permissions.has("ufls.publish");

  const [remarks, setRemarks] = useState("");
  const [publishError, setPublishError] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);

  const versionQuery = useQuery({
    queryKey: ["ufls", "version", versionId],
    queryFn: () => uflsApi.getVersion(versionId!),
    enabled: !!versionId,
  });

  const reviewQuery = useQuery({
    queryKey: ["ufls", "version", versionId, "publication-review"],
    queryFn: () => uflsApi.getPublicationReview(versionId!),
    enabled: !!versionId,
  });

  const summaryQuery = useQuery({
    queryKey: ["ufls", "version", versionId, "summary"],
    queryFn: () => uflsApi.getEngineeringSummary(versionId!),
    enabled: !!versionId,
  });

  const handlePublish = async () => {
    if (!versionId) return;
    setIsPublishing(true);
    setPublishError(null);
    try {
      await uflsApi.publish(versionId, {
        publication_event_id: crypto.randomUUID(),
        acknowledgements: [],
        remarks: remarks || null,
      });
      navigate(`/ufls/versions/${versionId}`);
    } catch (error) {
      setPublishError(error instanceof Error ? error.message : "Failed to publish.");
    } finally {
      setIsPublishing(false);
    }
  };

  if (versionQuery.isLoading || reviewQuery.isLoading) return <p>Loading publication review...</p>;
  if (versionQuery.isError || reviewQuery.isError || !versionQuery.data || !reviewQuery.data) {
    return <p role="alert">Failed to load publication review.</p>;
  }

  const version = versionQuery.data;
  const review = reviewQuery.data;
  const isDraft = version.lifecycle_status === "DRAFT";

  return (
    <section>
      <h2>Publication Review — Version {version.version_number}</h2>
      <p>
        <Link to={`/ufls/versions/${version.version_id}`}>Back to Draft Editor</Link>
      </p>
      <p style={{ fontStyle: "italic", color: "#555" }}>
        These automated checks confirm structural completeness only. Passing every check does not
        replace engineering approval or judgement — the publishing Administrator still makes the
        engineering decision.
      </p>

      <h3>Publication Prerequisites</h3>
      <table>
        <thead>
          <tr>
            <th>Prerequisite</th>
            <th>Status</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          {review.prerequisites.map((prerequisite, index) => (
            <tr key={`${prerequisite.prerequisite_code}-${index}`}>
              <td>{prerequisite.prerequisite_code}</td>
              <td style={{ color: prerequisite.passed ? "#1a7f37" : "#cf222e", fontWeight: 600 }}>
                {prerequisite.passed ? "Pass" : "Blocking"}
              </td>
              <td>{prerequisite.description}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Findings</h3>
      {review.findings.length === 0 && <p>No findings.</p>}
      {review.findings.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Type</th>
              <th>Severity</th>
              <th>Description</th>
              <th>Affected Object</th>
            </tr>
          </thead>
          <tbody>
            {review.findings.map((finding, index) => (
              <tr key={index}>
                <td>{finding.finding_type}</td>
                <td>{finding.severity}</td>
                <td>{finding.description}</td>
                <td>
                  {finding.affected_object_type} / {finding.affected_object_id}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {summaryQuery.data && (
        <>
          <h3>Engineering Summary</h3>
          <dl>
            <dt>Total Target MW</dt>
            <dd>{summaryQuery.data.total_target_mw}</dd>
            <dt>Direct Assignments</dt>
            <dd>{summaryQuery.data.direct_assignment_count}</dd>
            <dt>Boundary Pocket Assignments</dt>
            <dd>{summaryQuery.data.pocket_assignment_count}</dd>
            <dt>Distinct Substations</dt>
            <dd>{summaryQuery.data.distinct_substation_count}</dd>
            <dt>Unresolved Findings</dt>
            <dd>{summaryQuery.data.unresolved_finding_count}</dd>
          </dl>
          <table>
            <thead>
              <tr>
                <th>Stage</th>
                <th>Target MW</th>
                <th>Direct</th>
                <th>Pocket</th>
              </tr>
            </thead>
            <tbody>
              {summaryQuery.data.stage_summaries.map((stage) => (
                <tr key={stage.ufls_stage_id}>
                  <td>{stage.stage_order}</td>
                  <td>{stage.target_mw ?? "Not set"}</td>
                  <td>{stage.direct_assignment_count}</td>
                  <td>{stage.pocket_assignment_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {isDraft && canPublish && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3>Publish</h3>
          <label>
            Remarks
            <textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} />
          </label>
          <div>
            <button
              type="button"
              onClick={handlePublish}
              disabled={!review.all_prerequisites_passed || isPublishing}
            >
              {isPublishing ? "Publishing..." : "Publish"}
            </button>
          </div>
          {!review.all_prerequisites_passed && (
            <p style={{ color: "#cf222e" }}>
              Publication is blocked until every prerequisite above passes.
            </p>
          )}
          {publishError && <p role="alert">{publishError}</p>}
        </div>
      )}
      {isDraft && !canPublish && (
        <p style={{ color: "#555" }}>Publishing requires UFLS publish permission.</p>
      )}
      {!isDraft && <p style={{ color: "#555" }}>This version is no longer a Draft.</p>}
    </section>
  );
}
