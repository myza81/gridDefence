import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import { useAuth } from "../../iam/AuthContext";
import { sensitiveCustomerRegistryApi } from "../api";
import { TerminalMultiSelect } from "../components/TerminalMultiSelect";
import { describeTerminalResolution } from "../displayHelpers";

/** Detail view + metadata edit + the three lifecycle actions (Archive /
 * Reactivate / Entered in Error) + audit history (implementation spec
 * §14, Increments 9-10; ADR-013 UAT change request). `Entered in Error`
 * is terminal — the edit form, terminal association section, and every
 * lifecycle action are hidden once a facility reaches that state,
 * mirroring the backend's own enforcement
 * (`FacilityEnteredInErrorImmutableError`). Transformer Terminal
 * association changes are a separate section from metadata edit (name /
 * sector / classification / remarks) — the terminal set is replaced as a
 * whole via `PUT .../terminals`, requiring a non-empty reason whenever the
 * set actually changes (Correction 5, generalised) — enforced client-side
 * as a defense-in-depth UX affordance, and authoritatively by the backend
 * regardless. */
export function FacilityDetailPage() {
  const { facilityId } = useParams<{ facilityId: string }>();
  const { permissions } = useAuth();
  const canWrite = permissions.has("sensitive_customer_registry.write");
  const queryClient = useQueryClient();

  const detailQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "facilities", facilityId],
    queryFn: () => sensitiveCustomerRegistryApi.getFacility(facilityId!),
    enabled: facilityId !== undefined,
  });

  const auditLogQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "facilities", facilityId, "audit-log"],
    queryFn: () => sensitiveCustomerRegistryApi.listAuditLog(facilityId!),
    enabled: facilityId !== undefined,
  });

  const sectorsQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "facility-sectors"],
    queryFn: sensitiveCustomerRegistryApi.listFacilitySectors,
  });
  const classificationsQuery = useQuery({
    queryKey: ["sensitive-customer-registry", "sensitivity-classifications"],
    queryFn: sensitiveCustomerRegistryApi.listSensitivityClassifications,
  });
  const terminalIdentitiesQuery = useQuery({
    queryKey: ["equipment-registry", "transformer-terminal-identities"],
    queryFn: equipmentRegistryApi.listTransformerTerminalIdentities,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: ["sensitive-customer-registry", "facilities", facilityId],
    });
  };

  const [name, setName] = useState("");
  const [facilitySectorId, setFacilitySectorId] = useState("");
  const [sensitivityClassificationId, setSensitivityClassificationId] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editReason, setEditReason] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  const [terminalIds, setTerminalIds] = useState<string[]>([]);
  const [terminalsReason, setTerminalsReason] = useState("");
  const [terminalsError, setTerminalsError] = useState<string | null>(null);

  useEffect(() => {
    if (detailQuery.data) {
      setName(detailQuery.data.name);
      setFacilitySectorId(String(detailQuery.data.facility_sector.id));
      setSensitivityClassificationId(String(detailQuery.data.sensitivity_classification.id));
      setRemarks(detailQuery.data.remarks ?? "");
      setTerminalIds(
        detailQuery.data.transformer_terminals.map((t) => t.transformer_terminal_id),
      );
    }
  }, [detailQuery.data]);

  const updateMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.updateFacility(facilityId!, {
        name,
        facility_sector_id: Number(facilitySectorId),
        sensitivity_classification_id: Number(sensitivityClassificationId),
        remarks: remarks || null,
        change_reason: editReason || null,
      }),
    onSuccess: () => {
      setEditError(null);
      invalidate();
    },
    onError: (err: unknown) =>
      setEditError(
        err instanceof ApiError ? err.message : "Failed to update sensitive facility record.",
      ),
  });

  function handleEditSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    updateMutation.mutate();
  }

  const currentTerminalIds = (detailQuery.data?.transformer_terminals ?? []).map(
    (t) => t.transformer_terminal_id,
  );
  const terminalsChanged =
    terminalIds.length !== currentTerminalIds.length ||
    !terminalIds.every((id) => currentTerminalIds.includes(id));

  const setTerminalsMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.setFacilityTerminals(facilityId!, {
        transformer_terminal_ids: terminalIds,
        change_reason: terminalsReason || null,
      }),
    onSuccess: () => {
      setTerminalsError(null);
      setTerminalsReason("");
      invalidate();
    },
    onError: (err: unknown) =>
      setTerminalsError(
        err instanceof ApiError
          ? err.message
          : "Failed to update the Transformer Terminal association(s).",
      ),
  });

  function handleTerminalsSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setTerminalsMutation.mutate();
  }

  const [lifecycleReason, setLifecycleReason] = useState("");
  const [lifecycleError, setLifecycleError] = useState<string | null>(null);

  const archiveMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.archiveFacility(facilityId!, { change_reason: lifecycleReason }),
    onSuccess: () => {
      setLifecycleError(null);
      setLifecycleReason("");
      invalidate();
    },
    onError: (err: unknown) =>
      setLifecycleError(err instanceof ApiError ? err.message : "Failed to archive."),
  });

  const reactivateMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.reactivateFacility(facilityId!, {
        change_reason: lifecycleReason,
      }),
    onSuccess: () => {
      setLifecycleError(null);
      setLifecycleReason("");
      invalidate();
    },
    onError: (err: unknown) =>
      setLifecycleError(err instanceof ApiError ? err.message : "Failed to reactivate."),
  });

  const enteredInErrorMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.markFacilityEnteredInError(facilityId!, {
        change_reason: lifecycleReason,
      }),
    onSuccess: () => {
      setLifecycleError(null);
      setLifecycleReason("");
      invalidate();
    },
    onError: (err: unknown) =>
      setLifecycleError(err instanceof ApiError ? err.message : "Failed to mark entered in error."),
  });

  if (detailQuery.isLoading) {
    return <p>Loading sensitive facility record...</p>;
  }
  if (detailQuery.isError || !detailQuery.data) {
    return <p role="alert">Sensitive facility record not found.</p>;
  }

  const facility = detailQuery.data;
  const isEnteredInError = facility.lifecycle_status === "ENTERED_IN_ERROR";
  const isArchived = facility.lifecycle_status === "ARCHIVED";

  return (
    <section>
      <h2>Sensitive Facility — {facility.name}</h2>
      <dl>
        <dt>Facility Name</dt>
        <dd>{facility.name}</dd>
        <dt>Sector</dt>
        <dd>{facility.facility_sector.label}</dd>
        <dt>Sensitivity Classification</dt>
        <dd>{facility.sensitivity_classification.label}</dd>
        <dt>Supply Point(s)</dt>
        <dd>
          {facility.transformer_terminals.length === 0
            ? describeTerminalResolution(facility.transformer_terminal_resolution)
            : `${facility.transformer_terminals.length} currently associated Transformer Terminal(s)`}
        </dd>
        <dt>Lifecycle Status</dt>
        <dd>{facility.lifecycle_status}</dd>
        <dt>Remarks</dt>
        <dd>{facility.remarks ?? "—"}</dd>
        <dt>Created by</dt>
        <dd>{facility.created_by?.username ?? "—"}</dd>
        <dt>Updated by</dt>
        <dd>{facility.updated_by?.username ?? "—"}</dd>
      </dl>

      <h3>Transformer Terminal(s)</h3>
      {facility.transformer_terminals.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Substation</th>
              <th>Voltage</th>
              <th>Transformer</th>
              <th>Terminal</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {facility.transformer_terminals.map((association) => (
              <tr key={association.transformer_terminal_id}>
                <td>{association.substation_mnemonic ?? "—"}</td>
                <td>{association.voltage_level_label ?? "—"}</td>
                <td>{association.bay_label ?? "—"}</td>
                <td>{association.side ?? "—"}</td>
                <td>
                  {association.resolution === "UNRESOLVED"
                    ? "Terminal could not be resolved"
                    : "Resolved"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {facility.transformer_terminals.length === 0 && (
        <p>{describeTerminalResolution(facility.transformer_terminal_resolution)}</p>
      )}

      {canWrite && !isEnteredInError && (
        <form onSubmit={handleTerminalsSubmit} style={{ marginTop: "0.75rem" }}>
          <TerminalMultiSelect
            identities={terminalIdentitiesQuery.data ?? []}
            selectedIds={terminalIds}
            onChange={setTerminalIds}
            isLoading={terminalIdentitiesQuery.isLoading}
          />
          <div style={{ marginTop: "0.5rem" }}>
            <label htmlFor="scr-terminals-reason">
              Change reason (required if changing the Transformer Terminal association(s))
            </label>
            <br />
            <input
              id="scr-terminals-reason"
              value={terminalsReason}
              onChange={(e) => setTerminalsReason(e.target.value)}
            />
          </div>
          {terminalsError && <p role="alert">{terminalsError}</p>}
          <button
            type="submit"
            disabled={
              setTerminalsMutation.isPending ||
              !terminalsChanged ||
              (terminalsChanged && terminalsReason.trim() === "")
            }
          >
            Save Transformer Terminal(s)
          </button>
        </form>
      )}

      {isEnteredInError && (
        <p>
          This record is entered in error and is permanently terminal — it cannot be edited or
          transitioned further.
        </p>
      )}

      {canWrite && !isEnteredInError && (
        <>
          <h3>Lifecycle</h3>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
            <input
              aria-label="Lifecycle change reason"
              placeholder="Reason (required)"
              value={lifecycleReason}
              onChange={(e) => setLifecycleReason(e.target.value)}
            />
            {!isArchived && (
              <button
                type="button"
                onClick={() => archiveMutation.mutate()}
                disabled={archiveMutation.isPending || lifecycleReason.trim() === ""}
              >
                Archive
              </button>
            )}
            {isArchived && (
              <button
                type="button"
                onClick={() => reactivateMutation.mutate()}
                disabled={reactivateMutation.isPending || lifecycleReason.trim() === ""}
              >
                Reactivate
              </button>
            )}
            <button
              type="button"
              onClick={() => enteredInErrorMutation.mutate()}
              disabled={enteredInErrorMutation.isPending || lifecycleReason.trim() === ""}
            >
              Mark Entered in Error
            </button>
          </div>
          {lifecycleError && <p role="alert">{lifecycleError}</p>}

          <h3>Edit</h3>
          <form onSubmit={handleEditSubmit}>
            <div style={{ marginBottom: "0.5rem" }}>
              <label htmlFor="edit-scr-name">Facility Name</label>
              <br />
              <input
                id="edit-scr-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={255}
              />
            </div>
            <div style={{ marginBottom: "0.5rem" }}>
              <label htmlFor="edit-scr-sector">Sector</label>
              <br />
              <select
                id="edit-scr-sector"
                value={facilitySectorId}
                onChange={(e) => setFacilitySectorId(e.target.value)}
              >
                {sectorsQuery.data?.map((sector) => (
                  <option key={sector.id} value={sector.id}>
                    {sector.label}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: "0.5rem" }}>
              <label htmlFor="edit-scr-classification">Sensitivity Classification</label>
              <br />
              <select
                id="edit-scr-classification"
                value={sensitivityClassificationId}
                onChange={(e) => setSensitivityClassificationId(e.target.value)}
              >
                {classificationsQuery.data?.map((classification) => (
                  <option key={classification.id} value={classification.id}>
                    {classification.label}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: "0.5rem" }}>
              <label htmlFor="edit-scr-remarks">Remarks</label>
              <br />
              <textarea
                id="edit-scr-remarks"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
              />
            </div>
            <div style={{ marginBottom: "0.5rem" }}>
              <label htmlFor="edit-scr-reason">Change reason (optional)</label>
              <br />
              <input
                id="edit-scr-reason"
                value={editReason}
                onChange={(e) => setEditReason(e.target.value)}
              />
            </div>
            {editError && <p role="alert">{editError}</p>}
            <button type="submit" disabled={updateMutation.isPending}>
              Save changes
            </button>
          </form>
        </>
      )}

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
