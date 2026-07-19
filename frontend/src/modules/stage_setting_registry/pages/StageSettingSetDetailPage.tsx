import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { useReferenceData } from "../../../reference_data/useReferenceData";
import { useAuth } from "../../iam/AuthContext";
import { stageSettingRegistryApi } from "../api";
import type {
  StageSettingDetail,
  StageSettingSetDetail,
  StageSettingTriggerDetail,
} from "../types";

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  ENTERED_IN_ERROR: "Entered in Error",
};

function thresholdLabel(schemeType: string): string {
  return schemeType === "UVLS" ? "Voltage Threshold (p.u.)" : "Frequency Threshold (Hz)";
}

/**
 * Stage Setting Set Detail (stage-setting-set-architecture.md §6, §7, §10)
 * — metadata, ordered Stage Settings, and lifecycle actions. Draft-only
 * edit affordances (add/update/remove/reorder settings, edit description);
 * Published and Entered in Error render strictly read-only (§6 — both are
 * immutable). Publish and Entered in Error each require their own
 * dedicated permission, distinct from ordinary Draft-editing access.
 */
export function StageSettingSetDetailPage() {
  const { stageSettingSetId } = useParams<{ stageSettingSetId: string }>();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { permissions } = useAuth();
  const canManage = permissions.has("stage_setting_registry.manage");
  const canPublish = permissions.has("stage_setting_registry.publish");
  const canEnterInError = permissions.has("stage_setting_registry.enter_in_error");
  const referenceData = useReferenceData();

  const detailQuery = useQuery({
    queryKey: ["stage-setting-sets", stageSettingSetId],
    queryFn: () => stageSettingRegistryApi.get(stageSettingSetId!),
    enabled: !!stageSettingSetId,
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ["stage-setting-sets", stageSettingSetId] });

  const [publishError, setPublishError] = useState<string | null>(null);
  const [isPublishing, setIsPublishing] = useState(false);
  const [errorReason, setErrorReason] = useState("");
  const [enterInErrorError, setEnterInErrorError] = useState<string | null>(null);

  const handlePublish = async () => {
    if (!stageSettingSetId) return;
    setPublishError(null);
    setIsPublishing(true);
    try {
      await stageSettingRegistryApi.publish(stageSettingSetId);
      invalidate();
    } catch (error) {
      setPublishError(error instanceof Error ? error.message : "Failed to publish.");
    } finally {
      setIsPublishing(false);
    }
  };

  const handleEnterInError = async () => {
    if (!stageSettingSetId) return;
    setEnterInErrorError(null);
    try {
      await stageSettingRegistryApi.enterInError(stageSettingSetId, { change_reason: errorReason });
      setErrorReason("");
      invalidate();
    } catch (error) {
      setEnterInErrorError(error instanceof Error ? error.message : "Failed to mark Entered in Error.");
    }
  };

  if (detailQuery.isLoading) return <p>Loading Stage Setting Set...</p>;
  if (detailQuery.isError || !detailQuery.data) {
    return <p role="alert">Failed to load Stage Setting Set.</p>;
  }

  const detail = detailQuery.data;
  const isDraft = detail.status === "DRAFT";

  return (
    <section>
      <p>
        <Link to="/stage-setting-sets">Back to Stage Setting Registry</Link>
      </p>
      <h2>
        {detail.scheme_type} Stage Setting Set — {detail.description ?? "(no description)"}
      </h2>
      <p>
        Status: <strong>{STATUS_LABELS[detail.status]}</strong>
      </p>

      {isDraft && (
        <DeleteDraftSection
          detail={detail}
          canManage={canManage}
          onDeleted={() => navigate("/stage-setting-sets")}
        />
      )}

      <MetadataSection detail={detail} isDraft={isDraft} canManage={canManage} onSaved={invalidate} />

      <h3>Stages</h3>
      {detail.settings.length === 0 && <p>No stages yet.</p>}
      {detail.settings.length > 0 && (
        <StagesList
          detail={detail}
          canManage={canManage && isDraft}
          regions={referenceData.regions.data ?? []}
          onChanged={invalidate}
        />
      )}

      {isDraft && canManage && (
        <AddStageForm
          detail={detail}
          regions={referenceData.regions.data ?? []}
          onAdded={invalidate}
        />
      )}

      {isDraft && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3>Publish</h3>
          {detail.settings.length === 0 && (
            <p style={{ color: "#9a6700" }}>At least one Stage Setting is required to publish.</p>
          )}
          {canPublish ? (
            <>
              <button
                type="button"
                onClick={handlePublish}
                disabled={isPublishing || detail.settings.length === 0}
              >
                {isPublishing ? "Publishing..." : "Publish"}
              </button>
              <p style={{ fontSize: "0.85rem", color: "#555" }}>
                Publishing freezes this Stage Setting Set's structure permanently — it becomes
                referenceable by any number of UFLS/UVLS Scheme Versions, and can no longer be
                edited.
              </p>
              {publishError && <p role="alert">{publishError}</p>}
            </>
          ) : (
            <p style={{ color: "#555", fontSize: "0.9rem" }}>
              Publishing requires Stage Setting Registry publish permission.
            </p>
          )}
        </div>
      )}

      {detail.status === "PUBLISHED" && (
        <div style={{ marginTop: "1.5rem" }}>
          <h3>Mark Entered in Error</h3>
          {canEnterInError ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", maxWidth: "28rem" }}>
              <label>
                Reason (mandatory)
                <textarea value={errorReason} onChange={(e) => setErrorReason(e.target.value)} />
              </label>
              <button type="button" onClick={handleEnterInError} disabled={!errorReason.trim()}>
                Mark Entered in Error
              </button>
              <p style={{ fontSize: "0.85rem", color: "#555" }}>
                An administrative correction for a set that should never have been published.
                Scheme Versions already Published against this set are unaffected; any Draft
                Scheme Version still referencing it can no longer be published until it selects a
                different, Published set.
              </p>
              {enterInErrorError && <p role="alert">{enterInErrorError}</p>}
            </div>
          ) : (
            <p style={{ color: "#555", fontSize: "0.9rem" }}>
              Marking Entered in Error requires Stage Setting Registry enter-in-error permission.
            </p>
          )}
        </div>
      )}
    </section>
  );
}

function DeleteDraftSection({
  detail,
  canManage,
  onDeleted,
}: {
  detail: StageSettingSetDetail;
  canManage: boolean;
  onDeleted: () => void;
}) {
  const [isConfirming, setIsConfirming] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!canManage) {
    return null;
  }

  const handleDelete = async () => {
    setError(null);
    setIsDeleting(true);
    try {
      await stageSettingRegistryApi.deleteDraft(detail.stage_setting_set_id);
      onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to delete this Draft.");
      setIsDeleting(false);
    }
  };

  if (!isConfirming) {
    return (
      <div style={{ marginBottom: "1rem" }}>
        <button type="button" onClick={() => setIsConfirming(true)}>
          Delete Draft
        </button>
      </div>
    );
  }

  return (
    <div
      style={{
        marginBottom: "1rem",
        padding: "0.75rem",
        border: "1px solid #cf222e",
        borderRadius: "6px",
        maxWidth: "36rem",
      }}
    >
      <p>
        This Stage Setting Set has never been Published — deleting it is permanent and cannot be
        undone. Are you sure you want to delete this Draft?
      </p>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button type="button" onClick={handleDelete} disabled={isDeleting}>
          {isDeleting ? "Deleting..." : "Confirm Delete"}
        </button>
        <button type="button" onClick={() => setIsConfirming(false)} disabled={isDeleting}>
          Cancel
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

function MetadataSection({
  detail,
  isDraft,
  canManage,
  onSaved,
}: {
  detail: StageSettingSetDetail;
  isDraft: boolean;
  canManage: boolean;
  onSaved: () => void;
}) {
  const [description, setDescription] = useState(detail.description ?? "");
  const [error, setError] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  if (!isDraft || !canManage) {
    return (
      <dl>
        <dt>Created</dt>
        <dd>
          {new Date(detail.created_at).toLocaleString()}
          {detail.created_by ? ` by ${detail.created_by.display_name}` : ""}
        </dd>
        <dt>Last Updated</dt>
        <dd>
          {new Date(detail.updated_at).toLocaleString()}
          {detail.updated_by ? ` by ${detail.updated_by.display_name}` : ""}
        </dd>
      </dl>
    );
  }

  const handleSave = async () => {
    setError(null);
    setIsSaving(true);
    try {
      await stageSettingRegistryApi.update(detail.stage_setting_set_id, { description });
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to save.");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", maxWidth: "32rem" }}>
      <label style={{ flex: 1 }}>
        Description
        <input value={description} onChange={(e) => setDescription(e.target.value)} />
      </label>
      <button type="button" onClick={handleSave} disabled={isSaving}>
        Save
      </button>
      {error && <span role="alert">{error}</span>}
    </div>
  );
}

/**
 * Stages grouped by region scope (grid-wide null-scope group included as
 * its own group), sorted by stage_order within each group — mirrors the
 * backend's own per-scope monotonicity grouping
 * (stage-setting-set-architecture.md §7 rule 4). Each stage is rendered as
 * its own card with its operating criteria (triggers, ADR-025) nested
 * beneath it — never as a flat table row, so a stage with several
 * operating points never reads as several stages.
 */
function StagesList({
  detail,
  canManage,
  regions,
  onChanged,
}: {
  detail: StageSettingSetDetail;
  canManage: boolean;
  regions: { region_id: number; label: string }[];
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);

  const regionLabel = (regionScopeId: number | null): string => {
    if (regionScopeId === null) return "Grid-wide";
    return regions.find((r) => r.region_id === regionScopeId)?.label ?? String(regionScopeId);
  };

  const groups = new Map<number | null, StageSettingDetail[]>();
  for (const setting of detail.settings) {
    const key = setting.region_scope_id;
    const list = groups.get(key) ?? [];
    list.push(setting);
    groups.set(key, list);
  }
  for (const list of groups.values()) {
    list.sort((a, b) => a.stage_order - b.stage_order);
  }

  const handleRemoveStage = async (setting: StageSettingDetail) => {
    setError(null);
    try {
      await stageSettingRegistryApi.removeSetting(detail.stage_setting_set_id, setting.stage_setting_id);
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove stage.");
    }
  };

  const handleMoveStage = async (
    group: StageSettingDetail[],
    index: number,
    direction: -1 | 1,
  ) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= group.length) return;
    const reordered = [...group];
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    setError(null);
    try {
      await stageSettingRegistryApi.reorderSettings(detail.stage_setting_set_id, {
        region_scope_id: group[0].region_scope_id,
        ordered_stage_setting_ids: reordered.map((s) => s.stage_setting_id),
      });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reorder stages.");
    }
  };

  return (
    <div>
      {Array.from(groups.entries()).map(([regionScopeId, group]) => (
        <div key={regionScopeId ?? "grid-wide"} style={{ marginBottom: "1.5rem" }}>
          <p style={{ fontWeight: 600, marginBottom: "0.5rem" }}>{regionLabel(regionScopeId)}</p>
          {group.map((setting, index) => (
            <StageCard
              key={setting.stage_setting_id}
              stageSettingSetId={detail.stage_setting_set_id}
              schemeType={detail.scheme_type}
              setting={setting}
              canManage={canManage}
              onChanged={onChanged}
              onRemoveStage={() => handleRemoveStage(setting)}
              onMoveUp={index > 0 ? () => handleMoveStage(group, index, -1) : undefined}
              onMoveDown={
                index < group.length - 1 ? () => handleMoveStage(group, index, 1) : undefined
              }
            />
          ))}
        </div>
      ))}
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

function StageCard({
  stageSettingSetId,
  schemeType,
  setting,
  canManage,
  onChanged,
  onRemoveStage,
  onMoveUp,
  onMoveDown,
}: {
  stageSettingSetId: string;
  schemeType: string;
  setting: StageSettingDetail;
  canManage: boolean;
  onChanged: () => void;
  onRemoveStage: () => void;
  onMoveUp: (() => void) | undefined;
  onMoveDown: (() => void) | undefined;
}) {
  return (
    <div
      style={{
        border: "1px solid #d0d7de",
        borderRadius: "6px",
        padding: "0.75rem",
        marginBottom: "0.75rem",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
        <strong>Stage {setting.stage_order}</strong>
        {canManage && onMoveUp && (
          <button type="button" onClick={onMoveUp} aria-label={`Move stage ${setting.stage_order} up`}>
            ↑
          </button>
        )}
        {canManage && onMoveDown && (
          <button
            type="button"
            onClick={onMoveDown}
            aria-label={`Move stage ${setting.stage_order} down`}
          >
            ↓
          </button>
        )}
        {canManage && (
          <button type="button" onClick={onRemoveStage}>
            Remove Stage
          </button>
        )}
      </div>

      {setting.triggers.length === 0 && <p>No operating points yet.</p>}
      {setting.triggers.length > 0 && (
        <TriggersTable
          stageSettingSetId={stageSettingSetId}
          setting={setting}
          canManage={canManage}
          onChanged={onChanged}
        />
      )}

      {canManage && (
        <AddTriggerForm
          stageSettingSetId={stageSettingSetId}
          schemeType={schemeType}
          setting={setting}
          onAdded={onChanged}
        />
      )}
    </div>
  );
}

/**
 * A stage's own operating criteria (ADR-025) — any one of them being met
 * operates this same stage. Deliberately never labelled or numbered in a
 * way that could be read as separate stages.
 */
function TriggersTable({
  stageSettingSetId,
  setting,
  canManage,
  onChanged,
}: {
  stageSettingSetId: string;
  setting: StageSettingDetail;
  canManage: boolean;
  onChanged: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const triggers = [...setting.triggers].sort((a, b) => a.trigger_order - b.trigger_order);

  const handleRemove = async (trigger: StageSettingTriggerDetail) => {
    setError(null);
    try {
      await stageSettingRegistryApi.removeTrigger(
        stageSettingSetId,
        setting.stage_setting_id,
        trigger.stage_setting_trigger_id,
      );
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove operating point.");
    }
  };

  const handleMove = async (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= triggers.length) return;
    const reordered = [...triggers];
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    setError(null);
    try {
      await stageSettingRegistryApi.reorderTriggers(stageSettingSetId, setting.stage_setting_id, {
        ordered_trigger_ids: reordered.map((t) => t.stage_setting_trigger_id),
      });
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to reorder operating points.");
    }
  };

  return (
    <div>
      <table style={{ marginTop: "0.5rem" }}>
        <thead>
          <tr>
            <th>Order</th>
            <th>Threshold</th>
            <th>Time Delay (ms)</th>
            {canManage && <th></th>}
          </tr>
        </thead>
        <tbody>
          {triggers.map((trigger, index) => (
            <TriggerRow
              key={trigger.stage_setting_trigger_id}
              stageSettingSetId={stageSettingSetId}
              setting={setting}
              trigger={trigger}
              canManage={canManage}
              onRemove={() => handleRemove(trigger)}
              onMoveUp={index > 0 ? () => handleMove(index, -1) : undefined}
              onMoveDown={index < triggers.length - 1 ? () => handleMove(index, 1) : undefined}
              onChanged={onChanged}
            />
          ))}
        </tbody>
      </table>
      {error && <p role="alert">{error}</p>}
    </div>
  );
}

function TriggerRow({
  stageSettingSetId,
  setting,
  trigger,
  canManage,
  onChanged,
  onRemove,
  onMoveUp,
  onMoveDown,
}: {
  stageSettingSetId: string;
  setting: StageSettingDetail;
  trigger: StageSettingTriggerDetail;
  canManage: boolean;
  onChanged: () => void;
  onRemove: () => void;
  onMoveUp: (() => void) | undefined;
  onMoveDown: (() => void) | undefined;
}) {
  const [thresholdValue, setThresholdValue] = useState(String(trigger.threshold_value));
  const [timeDelayMs, setTimeDelayMs] = useState(String(trigger.time_delay_ms));
  const [error, setError] = useState<string | null>(null);

  if (!canManage) {
    return (
      <tr>
        <td>{trigger.trigger_order}</td>
        <td>
          {trigger.threshold_value} {trigger.threshold_unit}
        </td>
        <td>{trigger.time_delay_ms}</td>
      </tr>
    );
  }

  const handleSave = async () => {
    setError(null);
    try {
      await stageSettingRegistryApi.updateTrigger(
        stageSettingSetId,
        setting.stage_setting_id,
        trigger.stage_setting_trigger_id,
        {
          threshold_value: Number(thresholdValue),
          time_delay_ms: Number(timeDelayMs),
        },
      );
      onChanged();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update.");
    }
  };

  return (
    <tr>
      <td>
        {trigger.trigger_order}
        {onMoveUp && (
          <button
            type="button"
            onClick={onMoveUp}
            aria-label={`Move operating point ${trigger.trigger_order} up`}
          >
            ↑
          </button>
        )}
        {onMoveDown && (
          <button
            type="button"
            onClick={onMoveDown}
            aria-label={`Move operating point ${trigger.trigger_order} down`}
          >
            ↓
          </button>
        )}
      </td>
      <td>
        <input value={thresholdValue} onChange={(e) => setThresholdValue(e.target.value)} />
      </td>
      <td>
        <input value={timeDelayMs} onChange={(e) => setTimeDelayMs(e.target.value)} />
      </td>
      <td>
        <button type="button" onClick={handleSave}>
          Save
        </button>
        <button type="button" onClick={onRemove}>
          Remove
        </button>
        {error && <span role="alert">{error}</span>}
      </td>
    </tr>
  );
}

function AddTriggerForm({
  stageSettingSetId,
  schemeType,
  setting,
  onAdded,
}: {
  stageSettingSetId: string;
  schemeType: string;
  setting: StageSettingDetail;
  onAdded: () => void;
}) {
  const nextOrder = setting.triggers.length + 1;
  const [triggerOrder, setTriggerOrder] = useState(String(nextOrder));
  const [thresholdValue, setThresholdValue] = useState("");
  const [timeDelayMs, setTimeDelayMs] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await stageSettingRegistryApi.addTrigger(stageSettingSetId, setting.stage_setting_id, {
        trigger_order: Number(triggerOrder),
        threshold_value: Number(thresholdValue),
        time_delay_ms: Number(timeDelayMs),
      });
      setTriggerOrder(String(nextOrder + 1));
      setThresholdValue("");
      setTimeDelayMs("");
      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add operating point.");
    }
  };

  return (
    <form onSubmit={handleAdd} style={{ marginTop: "0.5rem" }}>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          Order
          <input
            type="number"
            min={1}
            value={triggerOrder}
            onChange={(e) => setTriggerOrder(e.target.value)}
            required
          />
        </label>
        <label>
          {thresholdLabel(schemeType)}
          <input
            value={thresholdValue}
            onChange={(e) => setThresholdValue(e.target.value)}
            required
          />
        </label>
        <label>
          Time Delay (ms)
          <input
            type="number"
            min={0}
            value={timeDelayMs}
            onChange={(e) => setTimeDelayMs(e.target.value)}
            required
          />
        </label>
        <button type="submit">Add Operating Point</button>
      </div>
      {error && <p role="alert">{error}</p>}
    </form>
  );
}

/**
 * Creates a new stage — identity, order, and (UVLS only) region scope
 * only. No threshold or time delay is asked for here: once the stage
 * exists, the engineer adds one or more operating points to it via each
 * stage's own "Add Operating Point" form (ADR-025) — never re-entering
 * stage_order to add a second operating point under an existing stage.
 */
function AddStageForm({
  detail,
  regions,
  onAdded,
}: {
  detail: StageSettingSetDetail;
  regions: { region_id: number; label: string }[];
  onAdded: () => void;
}) {
  const [stageOrder, setStageOrder] = useState("");
  const [regionScopeId, setRegionScopeId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleAdd = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    try {
      await stageSettingRegistryApi.addSetting(detail.stage_setting_set_id, {
        stage_order: Number(stageOrder),
        region_scope_id:
          detail.scheme_type === "UVLS" && regionScopeId ? Number(regionScopeId) : null,
      });
      setStageOrder("");
      setRegionScopeId("");
      onAdded();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add stage.");
    }
  };

  return (
    <form onSubmit={handleAdd} style={{ marginTop: "1rem", maxWidth: "36rem" }}>
      <h4>Add Stage</h4>
      <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "flex-end" }}>
        <label>
          Order
          <input
            type="number"
            min={1}
            value={stageOrder}
            onChange={(e) => setStageOrder(e.target.value)}
            required
          />
        </label>
        {detail.scheme_type === "UVLS" && (
          <label>
            Region Scope
            <select value={regionScopeId} onChange={(e) => setRegionScopeId(e.target.value)}>
              <option value="">Grid-wide (no region scope)</option>
              {regions.map((region) => (
                <option key={region.region_id} value={region.region_id}>
                  {region.label}
                </option>
              ))}
            </select>
          </label>
        )}
        <button type="submit">Add Stage</button>
      </div>
      {error && <p role="alert">{error}</p>}
      <p style={{ fontSize: "0.85rem", color: "#555" }}>
        Add at least one operating point below, on the new stage, before publishing.
      </p>
    </form>
  );
}
