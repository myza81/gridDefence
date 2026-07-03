import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { substationRegistryApi } from "../api";

export function SubstationDetailPage() {
  const { substationId } = useParams<{ substationId: string }>();
  const { permissions } = useAuth();
  const canWrite = permissions.has("substation_registry.write");
  const referenceData = useReferenceData();
  const queryClient = useQueryClient();

  const substationQuery = useQuery({
    queryKey: ["substation", substationId],
    queryFn: () => substationRegistryApi.getSubstation(substationId!),
    enabled: substationId !== undefined,
  });

  const aliasesQuery = useQuery({
    queryKey: ["substation", substationId, "aliases"],
    queryFn: () => substationRegistryApi.listAliases(substationId!),
    enabled: substationId !== undefined,
  });

  const auditLogQuery = useQuery({
    queryKey: ["substation", substationId, "audit-log"],
    queryFn: () => substationRegistryApi.listAuditLog(substationId!),
    enabled: substationId !== undefined,
  });

  const [mnemonic, setMnemonic] = useState("");
  const [officialName, setOfficialName] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    if (substationQuery.data) {
      setMnemonic(substationQuery.data.mnemonic);
      setOfficialName(substationQuery.data.official_name);
      setRemarks(substationQuery.data.remarks ?? "");
    }
  }, [substationQuery.data]);

  const invalidateSubstation = () => {
    void queryClient.invalidateQueries({ queryKey: ["substation", substationId] });
  };

  const updateMutation = useMutation({
    mutationFn: () =>
      substationRegistryApi.updateSubstation(substationId!, {
        mnemonic,
        official_name: officialName,
        remarks: remarks || null,
      }),
    onSuccess: () => {
      setEditError(null);
      invalidateSubstation();
    },
    onError: (err: unknown) =>
      setEditError(err instanceof ApiError ? err.message : "Failed to update substation."),
  });

  function handleEditSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    updateMutation.mutate();
  }

  const [statusId, setStatusId] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [statusError, setStatusError] = useState<string | null>(null);

  const statusMutation = useMutation({
    mutationFn: () =>
      substationRegistryApi.changeStatus(substationId!, {
        operational_status_id: Number(statusId),
        change_reason: changeReason || null,
      }),
    onSuccess: () => {
      setStatusError(null);
      setChangeReason("");
      invalidateSubstation();
    },
    onError: (err: unknown) =>
      setStatusError(err instanceof ApiError ? err.message : "Status change rejected."),
  });

  function handleStatusSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    statusMutation.mutate();
  }

  if (substationQuery.isLoading) {
    return <p>Loading substation...</p>;
  }
  if (substationQuery.isError || !substationQuery.data) {
    return <p role="alert">Substation not found.</p>;
  }

  const substation = substationQuery.data;

  return (
    <section>
      <h2>{substation.official_name}</h2>
      <dl>
        <dt>Mnemonic</dt>
        <dd>{substation.mnemonic}</dd>
        <dt>Voltage level</dt>
        <dd>{referenceData.voltageLevelsById.get(substation.voltage_level_id)?.label}</dd>
        <dt>Region</dt>
        <dd>{referenceData.regionsById.get(substation.region_id)?.label}</dd>
        <dt>State</dt>
        <dd>{referenceData.statesById.get(substation.state_id)?.label}</dd>
        <dt>Grid owner</dt>
        <dd>{referenceData.gridOwnersById.get(substation.grid_owner_id)?.label}</dd>
        <dt>Status</dt>
        <dd>{referenceData.operationalStatusesById.get(substation.operational_status_id)?.label}</dd>
        <dt>Created by</dt>
        <dd>{substation.created_by?.username ?? "—"}</dd>
        <dt>Updated by</dt>
        <dd>{substation.updated_by?.username ?? "—"}</dd>
      </dl>

      {canWrite && (
        <>
          <h3>Edit</h3>
          <form onSubmit={handleEditSubmit}>
            <div>
              <label htmlFor="edit-mnemonic">Mnemonic</label>
              <br />
              <input
                id="edit-mnemonic"
                value={mnemonic}
                onChange={(e) => setMnemonic(e.target.value)}
                maxLength={10}
              />
            </div>
            <div>
              <label htmlFor="edit-official-name">Official name</label>
              <br />
              <input
                id="edit-official-name"
                value={officialName}
                onChange={(e) => setOfficialName(e.target.value)}
                maxLength={150}
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

          <h3>Change status</h3>
          <form onSubmit={handleStatusSubmit}>
            <select
              aria-label="New status"
              value={statusId}
              onChange={(e) => setStatusId(e.target.value)}
              required
            >
              <option value="">Select new status...</option>
              {referenceData.operationalStatuses.map((status) => (
                <option key={status.operational_status_id} value={status.operational_status_id}>
                  {status.label}
                </option>
              ))}
            </select>
            <input
              aria-label="Change reason"
              placeholder="Reason (optional)"
              value={changeReason}
              onChange={(e) => setChangeReason(e.target.value)}
            />
            <button type="submit" disabled={statusMutation.isPending}>
              Apply
            </button>
            {statusError && <p role="alert">{statusError}</p>}
          </form>
        </>
      )}

      <h3>Alias history</h3>
      <ul>
        {(aliasesQuery.data ?? []).map((alias) => (
          <li key={alias.alias_id}>
            {alias.alias_mnemonic ?? alias.alias_name} (valid {alias.valid_from} –{" "}
            {alias.valid_to ?? "present"})
          </li>
        ))}
        {aliasesQuery.data?.length === 0 && <li>No prior aliases.</li>}
      </ul>

      <h3>Audit log</h3>
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
