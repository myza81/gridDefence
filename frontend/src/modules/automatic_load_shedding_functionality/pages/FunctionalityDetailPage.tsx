import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { automaticLoadSheddingFunctionalityApi } from "../api";
import { deriveFunctionLabel, formatTerminalIdentity } from "../displayHelpers";

/** Detail view + the one remaining lifecycle action (Decommission) +
 * editable metadata + audit/history view (module document §12, §17 UI
 * requirements). Status Model Refinement: Available/Assigned are always
 * computed by the backend from active UFLS/UVLS assignments — there is no
 * Activate/Deactivate action any more. A decommissioned record is
 * immutable — the metadata edit form and the Decommission action are
 * hidden once decommissioned, mirroring the backend's own enforcement
 * (module document §8, §18). */
export function FunctionalityDetailPage() {
  const { functionalityId } = useParams<{ functionalityId: string }>();
  const { permissions } = useAuth();
  const canWrite = permissions.has("automatic_load_shedding_functionality.write");
  const queryClient = useQueryClient();

  const detailQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", functionalityId],
    queryFn: () => automaticLoadSheddingFunctionalityApi.get(functionalityId!),
    enabled: functionalityId !== undefined,
  });

  const auditLogQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", functionalityId, "audit-log"],
    queryFn: () => automaticLoadSheddingFunctionalityApi.listAuditLog(functionalityId!),
    enabled: functionalityId !== undefined,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: ["automatic-load-shedding-functionality", functionalityId],
    });
  };

  const [uflsFunction, setUflsFunction] = useState(false);
  const [uvlsFunction, setUvlsFunction] = useState(false);
  const [relayMake, setRelayMake] = useState("");
  const [relayModel, setRelayModel] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    if (detailQuery.data) {
      setUflsFunction(detailQuery.data.ufls_function);
      setUvlsFunction(detailQuery.data.uvls_function);
      setRelayMake(detailQuery.data.relay_make ?? "");
      setRelayModel(detailQuery.data.relay_model ?? "");
      setRemarks(detailQuery.data.remarks ?? "");
    }
  }, [detailQuery.data]);

  const updateMutation = useMutation({
    mutationFn: () =>
      automaticLoadSheddingFunctionalityApi.update(functionalityId!, {
        ufls_function: uflsFunction,
        uvls_function: uvlsFunction,
        relay_make: relayMake || null,
        relay_model: relayModel || null,
        remarks: remarks || null,
      }),
    onSuccess: () => {
      setEditError(null);
      invalidate();
    },
    onError: (err: unknown) =>
      setEditError(err instanceof ApiError ? err.message : "Failed to update functionality record."),
  });

  function handleEditSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    updateMutation.mutate();
  }

  const [decommissionReason, setDecommissionReason] = useState("");
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);

  const decommissionMutation = useMutation({
    mutationFn: () =>
      automaticLoadSheddingFunctionalityApi.decommission(functionalityId!, {
        change_reason: decommissionReason,
      }),
    onSuccess: () => {
      setLifecycleError(null);
      setDecommissionReason("");
      invalidate();
    },
    onError: (err: unknown) =>
      setLifecycleError(err instanceof ApiError ? err.message : "Failed to decommission."),
  });

  if (detailQuery.isLoading) {
    return <p>Loading functionality record...</p>;
  }
  if (detailQuery.isError || !detailQuery.data) {
    return <p role="alert">Functionality record not found.</p>;
  }

  const functionality = detailQuery.data;
  const isDecommissioned = functionality.status === "DECOMMISSIONED";
  const terminalIdentity = formatTerminalIdentity(
    functionality.substation_mnemonic,
    functionality.voltage_level_label,
    functionality.bay_label,
  );

  return (
    <section>
      <h2>Automatic Load Shedding Functionality — {terminalIdentity}</h2>
      <dl>
        <dt>Terminal Identity</dt>
        <dd>{terminalIdentity}</dd>
        <dt>Substation</dt>
        <dd>
          {functionality.substation_mnemonic} — {functionality.substation_official_name}
        </dd>
        <dt>Terminal Type</dt>
        <dd>
          {functionality.target_type === "CIRCUIT_TERMINAL"
            ? "Circuit Terminal (Line Bay)"
            : "Transformer Terminal (Transformer Bay)"}
        </dd>
        <dt>Bay</dt>
        <dd>{functionality.bay_label}</dd>
        <dt>Voltage level</dt>
        <dd>{functionality.voltage_level_label}</dd>
        <dt>Automatic Load Shedding Function</dt>
        <dd>{deriveFunctionLabel(functionality.ufls_function, functionality.uvls_function)}</dd>
        <dt>Status</dt>
        <dd>{functionality.status}</dd>
        <dt>Relay make</dt>
        <dd>{functionality.relay_make ?? "—"}</dd>
        <dt>Relay model</dt>
        <dd>{functionality.relay_model ?? "—"}</dd>
        <dt>Remarks</dt>
        <dd>{functionality.remarks ?? "—"}</dd>
        <dt>Created by</dt>
        <dd>{functionality.created_by?.username ?? "—"}</dd>
        <dt>Updated by</dt>
        <dd>{functionality.updated_by?.username ?? "—"}</dd>
      </dl>

      {canWrite && !isDecommissioned && (
        <>
          <h3>Lifecycle</h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <input
              aria-label="Decommission reason"
              placeholder="Decommission reason (required)"
              value={decommissionReason}
              onChange={(e) => setDecommissionReason(e.target.value)}
            />
            <button
              type="button"
              onClick={() => decommissionMutation.mutate()}
              disabled={decommissionMutation.isPending || decommissionReason.trim() === ""}
            >
              Decommission
            </button>
          </div>
          {lifecycleError && <p role="alert">{lifecycleError}</p>}

          <h3>Edit</h3>
          <form onSubmit={handleEditSubmit}>
            <label>
              <input
                type="checkbox"
                checked={uflsFunction}
                onChange={(e) => setUflsFunction(e.target.checked)}
              />{" "}
              UFLS function
            </label>{" "}
            <label>
              <input
                type="checkbox"
                checked={uvlsFunction}
                onChange={(e) => setUvlsFunction(e.target.checked)}
              />{" "}
              UVLS function
            </label>
            <div style={{ marginTop: "0.5rem" }}>
              <label htmlFor="edit-relay-make">Relay make</label>
              <br />
              <input
                id="edit-relay-make"
                value={relayMake}
                onChange={(e) => setRelayMake(e.target.value)}
                maxLength={100}
              />
            </div>
            <div>
              <label htmlFor="edit-relay-model">Relay model</label>
              <br />
              <input
                id="edit-relay-model"
                value={relayModel}
                onChange={(e) => setRelayModel(e.target.value)}
                maxLength={100}
              />
            </div>
            <div>
              <label htmlFor="edit-remarks">Remarks</label>
              <br />
              <textarea
                id="edit-remarks"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
              />
            </div>
            {editError && <p role="alert">{editError}</p>}
            <button type="submit" disabled={updateMutation.isPending}>
              Save changes
            </button>
          </form>
        </>
      )}

      {isDecommissioned && <p>This record is decommissioned and cannot be edited.</p>}

      <h3>Audit log — {terminalIdentity}</h3>
      <ul>
        {(auditLogQuery.data?.items ?? []).map((entry) => (
          <li key={entry.log_id}>
            {entry.field_name}: {entry.old_value ?? "—"} → {entry.new_value ?? "—"} (
            {entry.changed_by?.username ?? "unknown"}, {entry.changed_at})
            {entry.change_reason ? ` — ${entry.change_reason}` : ""}
          </li>
        ))}
        {auditLogQuery.data?.items.length === 0 && <li>No changes recorded yet.</li>}
      </ul>
    </section>
  );
}
