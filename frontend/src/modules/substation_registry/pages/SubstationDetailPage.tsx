import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import type { VoltageYardSummary } from "../../equipment_registry/types";
import { substationRegistryApi } from "../api";

interface VoltageYardRowProps {
  yard: VoltageYardSummary;
  canWrite: boolean;
  onSaved: () => void;
}

/** One switchyard's editable metadata — commissioning_date/latitude/
 * longitude belong to the switchyard, not the parent Substation (Phase 3
 * UAT follow-up): a multi-voltage site may have switchyards commissioned
 * at different dates with slightly different GIS coordinates. The
 * substation and voltage level a switchyard represents are not editable
 * here — that would just be a different switchyard. */
function VoltageYardRow({ yard, canWrite, onSaved }: VoltageYardRowProps) {
  const [commissioningDate, setCommissioningDate] = useState(yard.commissioning_date ?? "");
  const [latitude, setLatitude] = useState(yard.latitude === null ? "" : String(yard.latitude));
  const [longitude, setLongitude] = useState(yard.longitude === null ? "" : String(yard.longitude));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setCommissioningDate(yard.commissioning_date ?? "");
    setLatitude(yard.latitude === null ? "" : String(yard.latitude));
    setLongitude(yard.longitude === null ? "" : String(yard.longitude));
  }, [yard.commissioning_date, yard.latitude, yard.longitude]);

  const updateMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateVoltageYard(yard.voltage_yard_id, {
        commissioning_date: commissioningDate || null,
        latitude: latitude === "" ? null : Number(latitude),
        longitude: longitude === "" ? null : Number(longitude),
      }),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Failed to update switchyard."),
  });

  if (!canWrite) {
    return (
      <li>
        {yard.voltage_level_label} — commissioned {yard.commissioning_date ?? "—"}, at{" "}
        {yard.latitude ?? "—"}, {yard.longitude ?? "—"}
      </li>
    );
  }

  return (
    <li>
      {yard.voltage_level_label}
      <div>
        <label htmlFor={`yard-commissioning-date-${yard.voltage_yard_id}`}>
          Commissioning date for {yard.voltage_level_label}
        </label>
        <br />
        <input
          id={`yard-commissioning-date-${yard.voltage_yard_id}`}
          aria-label={`Commissioning date for ${yard.voltage_level_label}`}
          type="date"
          value={commissioningDate}
          onChange={(e) => setCommissioningDate(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor={`yard-latitude-${yard.voltage_yard_id}`}>
          Latitude for {yard.voltage_level_label}
        </label>
        <br />
        <input
          id={`yard-latitude-${yard.voltage_yard_id}`}
          aria-label={`Latitude for ${yard.voltage_level_label}`}
          type="number"
          step="any"
          min={-90}
          max={90}
          value={latitude}
          onChange={(e) => setLatitude(e.target.value)}
        />
      </div>
      <div>
        <label htmlFor={`yard-longitude-${yard.voltage_yard_id}`}>
          Longitude for {yard.voltage_level_label}
        </label>
        <br />
        <input
          id={`yard-longitude-${yard.voltage_yard_id}`}
          aria-label={`Longitude for ${yard.voltage_level_label}`}
          type="number"
          step="any"
          min={-180}
          max={180}
          value={longitude}
          onChange={(e) => setLongitude(e.target.value)}
        />
      </div>
      <button
        type="button"
        onClick={() => updateMutation.mutate()}
        disabled={updateMutation.isPending}
      >
        Save
      </button>
      {error && <p role="alert">{error}</p>}
    </li>
  );
}

export function SubstationDetailPage() {
  const { substationId } = useParams<{ substationId: string }>();
  const { permissions } = useAuth();
  const canWrite = permissions.has("substation_registry.write");
  // Switchyards are owned by Equipment Registry, not Substation Registry
  // (equipment-registry-module.md §7.5a; ADR-008) — gated on that module's
  // own write permission, not substation_registry.write.
  const canManageVoltageYards = permissions.has("equipment_registry.write");
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

  const voltageYardsQuery = useQuery({
    queryKey: ["substation", substationId, "voltage-yards"],
    queryFn: () => equipmentRegistryApi.listVoltageYards(substationId!),
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

  const [newYardVoltageLevelId, setNewYardVoltageLevelId] = useState("");
  const [newYardCommissioningDate, setNewYardCommissioningDate] = useState("");
  const [newYardLatitude, setNewYardLatitude] = useState("");
  const [newYardLongitude, setNewYardLongitude] = useState("");
  const [newYardError, setNewYardError] = useState<string | null>(null);

  const invalidateVoltageYards = () => {
    void queryClient.invalidateQueries({ queryKey: ["substation", substationId, "voltage-yards"] });
  };

  const addVoltageYardMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.createVoltageYard({
        substation_id: substationId!,
        voltage_level_id: Number(newYardVoltageLevelId),
        commissioning_date: newYardCommissioningDate || null,
        latitude: newYardLatitude === "" ? null : Number(newYardLatitude),
        longitude: newYardLongitude === "" ? null : Number(newYardLongitude),
      }),
    onSuccess: () => {
      setNewYardError(null);
      setNewYardVoltageLevelId("");
      setNewYardCommissioningDate("");
      setNewYardLatitude("");
      setNewYardLongitude("");
      invalidateVoltageYards();
    },
    onError: (err: unknown) =>
      setNewYardError(err instanceof ApiError ? err.message : "Failed to add switchyard."),
  });

  function handleAddVoltageYardSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    addVoltageYardMutation.mutate();
  }

  if (substationQuery.isLoading) {
    return <p>Loading substation...</p>;
  }
  if (substationQuery.isError || !substationQuery.data) {
    return <p role="alert">Substation not found.</p>;
  }

  const substation = substationQuery.data;
  // Only offer voltage levels this substation does not already have a
  // switchyard at — the backend correctly rejects a duplicate (at most one
  // switchyard per substation per voltage level, equipment-registry-module.md
  // §7.5a), but an unfiltered dropdown lets a user pick an already-used
  // level on their very first attempt with no way to know it will fail
  // (found during Phase 3 UAT).
  const usedVoltageLevelIds = new Set((voltageYardsQuery.data ?? []).map((y) => y.voltage_level_id));
  const availableVoltageLevelsForNewYard = referenceData.voltageLevels.filter(
    (level) => !usedVoltageLevelIds.has(level.voltage_level_id),
  );

  return (
    <section>
      <h2>{substation.official_name}</h2>
      <dl>
        <dt>Mnemonic</dt>
        <dd>{substation.mnemonic}</dd>
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

      <h3>Switchyards</h3>
      <p>
        This is the authoritative representation of this substation&apos;s voltage level(s)
        (ADR-009) — a substation with more than one voltage level physically present (e.g. a
        275kV switchyard and a 132kV switchyard) has one row per voltage level here; circuit
        terminals connect to a specific switchyard, not the substation as a whole
        (equipment-registry-module.md §7.5a).
      </p>
      <ul data-testid="voltage-yards-list">
        {(voltageYardsQuery.data ?? []).map((yard) => (
          <VoltageYardRow
            key={yard.voltage_yard_id}
            yard={yard}
            canWrite={canManageVoltageYards}
            onSaved={invalidateVoltageYards}
          />
        ))}
        {voltageYardsQuery.data?.length === 0 && <li>No switchyards registered yet.</li>}
      </ul>
      {canManageVoltageYards && voltageYardsQuery.data !== undefined && (
        <>
          {availableVoltageLevelsForNewYard.length > 0 ? (
            <form onSubmit={handleAddVoltageYardSubmit}>
              <div>
                <label htmlFor="new-yard-voltage-level">New switchyard voltage level</label>
                <br />
                <select
                  id="new-yard-voltage-level"
                  aria-label="New switchyard voltage level"
                  value={newYardVoltageLevelId}
                  onChange={(e) => setNewYardVoltageLevelId(e.target.value)}
                  required
                >
                  <option value="">Select voltage level...</option>
                  {availableVoltageLevelsForNewYard.map((level) => (
                    <option key={level.voltage_level_id} value={level.voltage_level_id}>
                      {level.label}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="new-yard-commissioning-date">
                  New switchyard commissioning date (optional)
                </label>
                <br />
                <input
                  id="new-yard-commissioning-date"
                  aria-label="New switchyard commissioning date"
                  type="date"
                  value={newYardCommissioningDate}
                  onChange={(e) => setNewYardCommissioningDate(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="new-yard-latitude">New switchyard latitude (optional)</label>
                <br />
                <input
                  id="new-yard-latitude"
                  aria-label="New switchyard latitude"
                  type="number"
                  step="any"
                  min={-90}
                  max={90}
                  value={newYardLatitude}
                  onChange={(e) => setNewYardLatitude(e.target.value)}
                />
              </div>
              <div>
                <label htmlFor="new-yard-longitude">New switchyard longitude (optional)</label>
                <br />
                <input
                  id="new-yard-longitude"
                  aria-label="New switchyard longitude"
                  type="number"
                  step="any"
                  min={-180}
                  max={180}
                  value={newYardLongitude}
                  onChange={(e) => setNewYardLongitude(e.target.value)}
                />
              </div>
              <button type="submit" disabled={addVoltageYardMutation.isPending}>
                Add switchyard
              </button>
              {newYardError && <p role="alert">{newYardError}</p>}
            </form>
          ) : (
            <p>This substation already has a switchyard at every known voltage level.</p>
          )}
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
