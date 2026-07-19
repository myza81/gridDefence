import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { SchemeVersionHeader } from "../../../components/scheme-platform/SchemeVersionHeader";
import { SchemeVersionMetadataPanel } from "../../../components/scheme-platform/SchemeVersionMetadataPanel";
import { useAuth } from "../../iam/AuthContext";
import { stageSettingRegistryApi } from "../../stage_setting_registry/api";
import type { StageSettingTriggerDetail } from "../../stage_setting_registry/types";
import { uflsApi } from "../api";
import type { UflsStageDetail, UflsStageTriggerSummary } from "../types";

/**
 * Renders a stage's own operating criteria (ADR-025) as "48.1 Hz / 0 ms,
 * 49.3 Hz / 60,000 ms" — deliberately never phrased as separate stages;
 * any one criterion being met operates this same stage.
 */
function formatTriggers(
  triggers: (UflsStageTriggerSummary | StageSettingTriggerDetail)[],
): string {
  return triggers
    .slice()
    .sort((a, b) => a.trigger_order - b.trigger_order)
    .map((t) => `${t.threshold_value} ${t.threshold_unit} / ${Number(t.time_delay_ms).toLocaleString()} ms`)
    .join(", ");
}

/**
 * UFLS Draft Editor + Stage and Assignment Workspace (task Frontend Scope
 * §"UFLS Draft Editor", §"Stage and Assignment Workspace") — a single,
 * dense engineering page rather than several thin ones, since a stage's
 * own assignments are meaningless without the stage's own target MW and
 * threshold context alongside them. Draft-only edit affordances; every
 * other lifecycle state (Published/Superseded/Entered in Error) renders
 * strictly read-only (CLAUDE.md A12; task's own explicit instruction).
 */
export function UflsDraftEditorPage() {
  const { versionId } = useParams<{ versionId: string }>();
  const queryClient = useQueryClient();
  const { permissions } = useAuth();
  const canManage = permissions.has("ufls.manage");

  const versionQuery = useQuery({
    queryKey: ["ufls", "version", versionId],
    queryFn: () => uflsApi.getVersion(versionId!),
    enabled: !!versionId,
  });

  const stagesQuery = useQuery({
    queryKey: ["ufls", "version", versionId, "stages"],
    queryFn: () => uflsApi.listStages(versionId!),
    enabled: !!versionId,
  });

  const publishedSetsQuery = useQuery({
    queryKey: ["ufls", "stage-setting-sets", "published"],
    queryFn: () =>
      stageSettingRegistryApi.list({
        scheme_type: "UFLS",
        status_filter: "PUBLISHED",
        page_size: 200,
      }),
  });

  const version = versionQuery.data;
  const isDraft = version?.lifecycle_status === "DRAFT";

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["ufls", "version", versionId] });
    queryClient.invalidateQueries({ queryKey: ["ufls", "version", versionId, "stages"] });
  };

  if (versionQuery.isLoading) return <p>Loading version...</p>;
  if (versionQuery.isError || !version) return <p role="alert">Failed to load version.</p>;

  return (
    <section>
      <SchemeVersionHeader
        title={`UFLS Scheme Version`}
        versionNumber={version.version_number}
        lifecycleStatus={version.lifecycle_status}
      />
      <p>
        <Link to={`/ufls/schemes/${version.ufls_scheme_id}`}>Back to scheme</Link>
        {" · "}
        <Link to={`/ufls/versions/${version.version_id}/publication-review`}>
          Publication Review
        </Link>
      </p>

      <MetadataSection
        version={version}
        isDraft={isDraft}
        canManage={canManage}
        publishedSets={publishedSetsQuery.data?.items ?? []}
        publishedSetsLoaded={publishedSetsQuery.isSuccess}
        onSaved={invalidate}
      />

      <SchemeVersionMetadataPanel
        metadata={{
          versionId: version.version_id,
          schemeId: version.scheme_id,
          versionNumber: version.version_number,
          lifecycleStatus: version.lifecycle_status,
          publishedAt: version.published_at,
          publishedBy: version.published_by,
          supersededAt: version.superseded_at,
          enteredInErrorAt: version.entered_in_error_at,
          enteredInErrorBy: version.entered_in_error_by,
          enteredInErrorReason: version.entered_in_error_reason,
          engineeringRemarks: version.engineering_remarks,
          createdAt: version.created_at,
          updatedAt: version.updated_at,
        }}
      />

      <h3>Stages</h3>
      {!version.stage_setting_set_id && (
        <p style={{ color: "#9a6700" }}>
          No Stage Setting Set selected yet — select one above before adding stages.
        </p>
      )}
      {stagesQuery.isLoading && <p>Loading stages...</p>}
      {stagesQuery.isError && <p role="alert">Failed to load stages.</p>}
      {stagesQuery.data?.map((stage) => (
        <StageCard key={stage.ufls_stage_id} stage={stage} isDraft={isDraft} onChanged={invalidate} />
      ))}

      {isDraft && canManage && version.stage_setting_set_id && (
        <AddStageForm
          versionId={version.version_id}
          stageSettingSetId={version.stage_setting_set_id}
          existingStageSettingIds={new Set((stagesQuery.data ?? []).map((s) => s.stage_setting_id))}
          onAdded={invalidate}
        />
      )}
    </section>
  );
}

function MetadataSection({
  version,
  isDraft,
  canManage,
  publishedSets,
  publishedSetsLoaded,
  onSaved,
}: {
  version: NonNullable<ReturnType<typeof uflsApi.getVersion> extends Promise<infer T> ? T : never>;
  isDraft: boolean;
  canManage: boolean;
  publishedSets: { stage_setting_set_id: string; description: string | null }[];
  publishedSetsLoaded: boolean;
  onSaved: () => void;
}) {
  const [stageSettingSetId, setStageSettingSetId] = useState(version.stage_setting_set_id ?? "");
  const [studyReference, setStudyReference] = useState(version.study_reference ?? "");
  const [effectiveDate, setEffectiveDate] = useState(version.effective_date ?? "");
  const [remarks, setRemarks] = useState(version.engineering_remarks ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  if (!isDraft || !canManage) {
    return (
      <dl>
        <dt>Stage Setting Set</dt>
        <dd>{version.stage_setting_set_id ?? "None selected"}</dd>
        <dt>Study Reference</dt>
        <dd>{version.study_reference ?? "—"}</dd>
        <dt>Effective Date</dt>
        <dd>{version.effective_date ?? "—"}</dd>
      </dl>
    );
  }

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await uflsApi.updateVersionMetadata(version.version_id, {
        stage_setting_set_id: stageSettingSetId || null,
        study_reference: studyReference || null,
        effective_date: effectiveDate || null,
        engineering_remarks: remarks || null,
      });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save metadata.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxWidth: "32rem" }}>
      <label>
        Stage Setting Set (Published, UFLS)
        <select value={stageSettingSetId} onChange={(e) => setStageSettingSetId(e.target.value)}>
          <option value="">None selected</option>
          {publishedSets.map((set) => (
            <option key={set.stage_setting_set_id} value={set.stage_setting_set_id}>
              {set.description ?? set.stage_setting_set_id}
            </option>
          ))}
        </select>
      </label>
      {publishedSetsLoaded && publishedSets.length === 0 && (
        <p style={{ color: "#9a6700" }}>
          No Published UFLS Stage Setting Set exists yet — a stage structure (thresholds and time
          delays) must be created and published in the{" "}
          <Link to="/stage-setting-sets?scheme_type=UFLS">Stage Setting Registry</Link> before this
          Draft can be given any stages.
        </p>
      )}
      <label>
        Study Reference
        <input value={studyReference} onChange={(e) => setStudyReference(e.target.value)} />
      </label>
      <label>
        Effective Date
        <input type="date" value={effectiveDate} onChange={(e) => setEffectiveDate(e.target.value)} />
      </label>
      <label>
        Engineering Remarks
        <textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} />
      </label>
      {error && <p role="alert">{error}</p>}
      <button type="button" onClick={handleSave} disabled={isSaving}>
        {isSaving ? "Saving..." : "Save Metadata"}
      </button>
    </div>
  );
}

function StageCard({
  stage,
  isDraft,
  onChanged,
}: {
  stage: UflsStageDetail;
  isDraft: boolean;
  onChanged: () => void;
}) {
  const { permissions } = useAuth();
  const canManage = permissions.has("ufls.manage") && isDraft;

  return (
    <div style={{ border: "1px solid #d0d7de", borderRadius: "6px", padding: "1rem", marginBottom: "1rem" }}>
      <h4>Stage {stage.stage_order} — {formatTriggers(stage.triggers)}</h4>
      <TargetMwEditor stage={stage} canManage={canManage} onChanged={onChanged} />
      <DirectAssignmentsPanel stageId={stage.ufls_stage_id} canManage={canManage} onChanged={onChanged} />
      <PocketAssignmentsPanel stageId={stage.ufls_stage_id} canManage={canManage} onChanged={onChanged} />
      {canManage && (
        <button
          type="button"
          onClick={async () => {
            await uflsApi.removeStage(stage.ufls_stage_id);
            onChanged();
          }}
        >
          Remove Stage
        </button>
      )}
    </div>
  );
}

function TargetMwEditor({
  stage,
  canManage,
  onChanged,
}: {
  stage: UflsStageDetail;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [targetMw, setTargetMw] = useState(stage.target_mw ?? "");
  const [error, setError] = useState<string | null>(null);

  if (!canManage) {
    return <p>Target MW: {stage.target_mw ?? "Not set"}</p>;
  }

  const handleSave = async () => {
    setError(null);
    try {
      await uflsApi.updateStage(stage.ufls_stage_id, { target_mw: targetMw || null });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update target MW.");
    }
  };

  return (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
      <label>
        Target MW (external-study value)
        <input value={targetMw} onChange={(e) => setTargetMw(e.target.value)} />
      </label>
      <button type="button" onClick={handleSave}>
        Save
      </button>
      {error && <span role="alert">{error}</span>}
    </div>
  );
}

function DirectAssignmentsPanel({
  stageId,
  canManage,
  onChanged,
}: {
  stageId: string;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [terminalId, setTerminalId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const assignmentsQuery = useQuery({
    queryKey: ["ufls", "stage", stageId, "direct-assignments"],
    queryFn: () => uflsApi.listDirectAssignments(stageId),
  });

  const handleAdd = async () => {
    setError(null);
    try {
      await uflsApi.addDirectAssignment(stageId, { transformer_terminal_id: terminalId });
      setTerminalId("");
      onChanged();
      await assignmentsQuery.refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add direct assignment.");
    }
  };

  const handleRemove = async (assignmentId: string) => {
    await uflsApi.removeDirectAssignment(assignmentId);
    onChanged();
    await assignmentsQuery.refetch();
  };

  return (
    <div style={{ marginTop: "0.5rem" }}>
      <strong>Direct Assignments (Transformer Terminals)</strong>
      {assignmentsQuery.isLoading && <p>Loading assignments...</p>}
      {(assignmentsQuery.data?.length ?? 0) > 0 && (
        <table style={{ marginTop: "0.25rem", fontSize: "0.9rem" }}>
          <thead>
            <tr>
              <th>Substation</th>
              <th>Transformer Terminal ID</th>
              <th>Remarks</th>
              {canManage && <th></th>}
            </tr>
          </thead>
          <tbody>
            {assignmentsQuery.data!.map((assignment) => (
              <tr key={assignment.ufls_direct_assignment_id}>
                <td>{assignment.substation_mnemonic}</td>
                <td>{assignment.transformer_terminal_id}</td>
                <td>{assignment.remarks ?? "—"}</td>
                {canManage && (
                  <td>
                    <button
                      type="button"
                      onClick={() => handleRemove(assignment.ufls_direct_assignment_id)}
                    >
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {canManage && (
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
          <input
            placeholder="Transformer Terminal ID"
            value={terminalId}
            onChange={(e) => setTerminalId(e.target.value)}
          />
          <button type="button" onClick={handleAdd} disabled={!terminalId.trim()}>
            Add
          </button>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

function PocketAssignmentsPanel({
  stageId,
  canManage,
  onChanged,
}: {
  stageId: string;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [terminalIds, setTerminalIds] = useState("");
  const [error, setError] = useState<string | null>(null);

  const assignmentsQuery = useQuery({
    queryKey: ["ufls", "stage", stageId, "pocket-assignments"],
    queryFn: () => uflsApi.listPocketAssignments(stageId),
  });

  const handleAdd = async () => {
    setError(null);
    const ids = terminalIds
      .split(",")
      .map((id) => id.trim())
      .filter(Boolean);
    if (ids.length === 0) return;
    try {
      await uflsApi.addPocketAssignment(stageId, { circuit_terminal_ids: ids });
      setTerminalIds("");
      onChanged();
      await assignmentsQuery.refetch();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add Boundary Pocket assignment.");
    }
  };

  const handleRemove = async (assignmentId: string) => {
    await uflsApi.removePocketAssignment(assignmentId);
    onChanged();
    await assignmentsQuery.refetch();
  };

  return (
    <div style={{ marginTop: "0.5rem" }}>
      <strong>Boundary Pocket Assignments (Circuit Terminals — opening points)</strong>
      {assignmentsQuery.isLoading && <p>Loading assignments...</p>}
      {(assignmentsQuery.data?.length ?? 0) > 0 && (
        <table style={{ marginTop: "0.25rem", fontSize: "0.9rem" }}>
          <thead>
            <tr>
              <th>Opening Points (Circuit Terminal IDs)</th>
              <th>Remarks</th>
              {canManage && <th></th>}
            </tr>
          </thead>
          <tbody>
            {assignmentsQuery.data!.map((assignment) => (
              <tr key={assignment.ufls_pocket_assignment_id}>
                <td>{assignment.circuit_terminal_ids.join(", ")}</td>
                <td>{assignment.remarks ?? "—"}</td>
                {canManage && (
                  <td>
                    <button
                      type="button"
                      onClick={() => handleRemove(assignment.ufls_pocket_assignment_id)}
                    >
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {canManage && (
        <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.5rem" }}>
          <input
            placeholder="Circuit Terminal IDs, comma-separated"
            value={terminalIds}
            onChange={(e) => setTerminalIds(e.target.value)}
            style={{ minWidth: "20rem" }}
          />
          <button type="button" onClick={handleAdd} disabled={!terminalIds.trim()}>
            Add
          </button>
        </div>
      )}
      <p style={{ fontSize: "0.8rem", color: "#555" }}>
        Only forms an assignment if the selected opening points isolate a real island
        (boundary-pocket-architecture.md) — an ineffective selection is rejected.
      </p>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

function AddStageForm({
  versionId,
  stageSettingSetId,
  existingStageSettingIds,
  onAdded,
}: {
  versionId: string;
  stageSettingSetId: string;
  existingStageSettingIds: Set<string>;
  onAdded: () => void;
}) {
  const settingsQuery = useQuery({
    queryKey: ["ufls", "stage-setting-set", stageSettingSetId, "settings"],
    queryFn: () => stageSettingRegistryApi.listSettings(stageSettingSetId),
  });
  const [selectedSettingId, setSelectedSettingId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const availableSettings = (settingsQuery.data ?? []).filter(
    (setting) => !existingStageSettingIds.has(setting.stage_setting_id),
  );

  const handleAdd = async () => {
    if (!selectedSettingId) return;
    setError(null);
    try {
      await uflsApi.addStage(versionId, { stage_setting_id: selectedSettingId });
      setSelectedSettingId("");
      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add stage.");
    }
  };

  if (availableSettings.length === 0) {
    return <p>Every stage in the selected Stage Setting Set already exists in this version.</p>;
  }

  return (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
      <select value={selectedSettingId} onChange={(e) => setSelectedSettingId(e.target.value)}>
        <option value="">Select a stage to add</option>
        {availableSettings.map((setting) => (
          <option key={setting.stage_setting_id} value={setting.stage_setting_id}>
            Stage {setting.stage_order} — {formatTriggers(setting.triggers)}
          </option>
        ))}
      </select>
      <button type="button" onClick={handleAdd} disabled={!selectedSettingId}>
        Add Stage
      </button>
      {error && <span role="alert">{error}</span>}
    </div>
  );
}
