import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

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
  statusLabel: string;
  enteredInErrorStatusId: number | undefined;
}

/** One switchyard's editable metadata — commissioning_date/latitude/
 * longitude belong to the switchyard, not the parent Substation (Phase 3
 * UAT follow-up): a multi-voltage site may have switchyards commissioned
 * at different dates with slightly different GIS coordinates. The
 * substation and voltage level a switchyard represents are not editable
 * here — that would just be a different switchyard.
 *
 * "Mark as Entered in Error" (deletion/correction policy, Phase 3
 * follow-up) corrects a mistakenly-created switchyard — never a delete
 * button, since no hard delete exists for engineering registry records
 * (CLAUDE.md §11.6). Hidden once the yard is already corrected, where it is
 * replaced by "Restore Voltage Yard" (ADR-027): the two lifecycle actions
 * are mutually exclusive, each requires a reason and an explicit
 * confirmation, and neither is ever presented as a delete/undelete. */
function VoltageYardRow({
  yard,
  canWrite,
  onSaved,
  statusLabel,
  enteredInErrorStatusId,
}: VoltageYardRowProps) {
  const [commissioningDate, setCommissioningDate] = useState(yard.commissioning_date ?? "");
  const [latitude, setLatitude] = useState(yard.latitude === null ? "" : String(yard.latitude));
  const [longitude, setLongitude] = useState(yard.longitude === null ? "" : String(yard.longitude));
  const [error, setError] = useState<string | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);
  const [correctionReason, setCorrectionReason] = useState("");
  const [restoreReason, setRestoreReason] = useState("");
  const [restoreError, setRestoreError] = useState<string | null>(null);
  const [restoreMessage, setRestoreMessage] = useState<string | null>(null);

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

  const isEnteredInError = yard.operational_status_id === enteredInErrorStatusId;

  const correctionMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateVoltageYard(yard.voltage_yard_id, {
        operational_status_id: enteredInErrorStatusId,
        // Mandatory in both lifecycle directions (ADR-027).
        change_reason: correctionReason,
      }),
    onSuccess: () => {
      setCorrectionError(null);
      setCorrectionReason("");
      onSaved();
    },
    onError: (err: unknown) =>
      setCorrectionError(
        err instanceof ApiError ? err.message : "Failed to correct switchyard.",
      ),
  });

  /* Restoration (ADR-027) — a switchyard's identity is
     (substation, voltage level) and the uniqueness rule protecting it is
     status-blind, so a corrected yard can never be replaced. An accidental
     correction is therefore reversed with this explicit, audited command
     rather than being permanent. It always targets Active; it is never a
     delete reversal, and it never removes the original correction entry. */
  const restoreMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.restoreVoltageYard(yard.voltage_yard_id, {
        change_reason: restoreReason,
      }),
    onSuccess: () => {
      setRestoreError(null);
      setRestoreReason("");
      setRestoreMessage(`${yard.voltage_level_label} switchyard restored to Active.`);
      onSaved();
    },
    onError: (err: unknown) =>
      setRestoreError(
        err instanceof ApiError ? err.message : "Failed to restore switchyard.",
      ),
  });

  /* Exactly one lifecycle action is offered at a time: an active yard can be
     corrected, an entered-in-error yard can be restored. Never both. */
  const correctionControl =
    canWrite && !isEnteredInError && enteredInErrorStatusId !== undefined ? (
      <div>
        <label htmlFor={`yard-correction-reason-${yard.voltage_yard_id}`}>
          Reason for marking {yard.voltage_level_label} as Entered in Error
        </label>
        <br />
        <input
          id={`yard-correction-reason-${yard.voltage_yard_id}`}
          aria-label={`Reason for marking ${yard.voltage_level_label} as Entered in Error`}
          value={correctionReason}
          onChange={(e) => setCorrectionReason(e.target.value)}
        />
        <button
          type="button"
          onClick={() => {
            if (!correctionReason.trim()) {
              setCorrectionError("A reason is required to mark this switchyard as Entered in Error.");
              return;
            }
            if (
              !window.confirm(
                `Mark the ${yard.voltage_level_label} switchyard as Entered in Error? ` +
                  "It will be hidden from active views. This is recorded in the audit log.",
              )
            ) {
              return;
            }
            correctionMutation.mutate();
          }}
          disabled={correctionMutation.isPending}
        >
          Mark as Entered in Error
        </button>
        {correctionError && <p role="alert">{correctionError}</p>}
      </div>
    ) : null;

  const restoreControl =
    canWrite && isEnteredInError ? (
      <div>
        <p>
          This switchyard is marked Entered in Error. Restoring it returns it to{" "}
          <strong>Active</strong>. Its audit history is preserved.
        </p>
        <label htmlFor={`yard-restore-reason-${yard.voltage_yard_id}`}>
          Reason for restoring {yard.voltage_level_label}
        </label>
        <br />
        <input
          id={`yard-restore-reason-${yard.voltage_yard_id}`}
          aria-label={`Reason for restoring ${yard.voltage_level_label}`}
          value={restoreReason}
          onChange={(e) => setRestoreReason(e.target.value)}
        />
        <button
          type="button"
          onClick={() => {
            if (!restoreReason.trim()) {
              setRestoreError("A reason is required to restore this switchyard.");
              return;
            }
            if (
              !window.confirm(
                `Restore the ${yard.voltage_level_label} switchyard to Active? ` +
                  "This is recorded in the audit log; the original correction entry is kept.",
              )
            ) {
              return;
            }
            restoreMutation.mutate();
          }}
          disabled={restoreMutation.isPending}
        >
          Restore Voltage Yard
        </button>
        {restoreError && <p role="alert">{restoreError}</p>}
      </div>
    ) : null;

  if (!canWrite) {
    return (
      <li>
        {yard.voltage_level_label} ({statusLabel}) — commissioned{" "}
        {yard.commissioning_date ?? "—"}, at {yard.latitude ?? "—"}, {yard.longitude ?? "—"}
      </li>
    );
  }

  return (
    <li>
      {yard.voltage_level_label} ({statusLabel})
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
      {restoreMessage && <p role="status">{restoreMessage}</p>}
      {correctionControl}
      {restoreControl}
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

  // Always fetched with include_entered_in_error=true: usedVoltageLevelIds
  // (below) must account for a corrected yard's voltage level too, since
  // the database's uq_substation_voltage_yard constraint is not
  // status-aware — offering that level as "available" in the Add
  // Switchyard dropdown would just reproduce the exact duplicate-offered-
  // as-available defect Phase 3 UAT already found once (DuplicateVoltageYardError).
  // "Show entered-in-error switchyards" (deletion/correction policy, Phase
  // 3 follow-up) then filters what is actually *displayed* client-side —
  // corrected switchyards are hidden from the default view but must
  // remain reachable for audit purposes; this substation's own detail
  // page is the only place a switchyard is ever shown at all (it has no
  // separate detail page of its own).
  const [showEnteredInErrorYards, setShowEnteredInErrorYards] = useState(false);
  const voltageYardsQuery = useQuery({
    queryKey: ["substation", substationId, "voltage-yards"],
    queryFn: () =>
      equipmentRegistryApi.listVoltageYards({
        substation_id: substationId!,
        include_entered_in_error: true,
      }),
    enabled: substationId !== undefined,
  });
  const enteredInErrorStatusId = referenceData.operationalStatuses.find(
    (status) => status.code === "ENTERED_IN_ERROR",
  )?.operational_status_id;
  const visibleVoltageYards = (voltageYardsQuery.data ?? []).filter(
    (yard) => showEnteredInErrorYards || yard.operational_status_id !== enteredInErrorStatusId,
  );

  // "Which transformers are installed here" — a transformer is
  // substation-owned equipment (UAT correction), so this substation's own
  // detail page is where that question is answered, mirroring the
  // Switchyards section immediately below.
  const transformersQuery = useQuery({
    queryKey: ["substation", substationId, "transformers"],
    queryFn: () =>
      equipmentRegistryApi.listTransformers({ substation_id: substationId!, page_size: 200 }),
    enabled: substationId !== undefined,
  });

  // "Engineering Connectivity" — which circuits are connected to this
  // substation, derived from Circuit/CircuitTerminal/Substation only
  // (equipment-registry-module.md's Engineering Connectivity addendum).
  // This is the manually-maintained engineering baseline, distinct from
  // any future PSS/E-derived operational topology snapshot (Phase 4) —
  // deliberately not called "Live Topology" or "Operational Connectivity".
  const connectedCircuitsQuery = useQuery({
    queryKey: ["substation", substationId, "circuits"],
    queryFn: () =>
      equipmentRegistryApi.listCircuits({ substation_id: substationId!, page_size: 200 }),
    enabled: substationId !== undefined,
  });

  const [mnemonic, setMnemonic] = useState("");
  const [officialName, setOfficialName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [gmZoneId, setGmZoneId] = useState("");
  const [stateId, setStateId] = useState("");
  const [gridOwnerId, setGridOwnerId] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    if (substationQuery.data) {
      setMnemonic(substationQuery.data.mnemonic);
      setOfficialName(substationQuery.data.official_name);
      setRegionId(String(substationQuery.data.region_id));
      setGmZoneId(String(substationQuery.data.gm_zone_id));
      // State is optional (ADR-026) — a null state maps to the empty
      // "None" option, never the string "null".
      setStateId(
        substationQuery.data.state_id === null ? "" : String(substationQuery.data.state_id),
      );
      setGridOwnerId(String(substationQuery.data.grid_owner_id));
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
        region_id: Number(regionId),
        gm_zone_id: Number(gmZoneId),
        // State is optional (ADR-026) — an empty selection sends an
        // explicit null, which clears the substation's State; a value
        // sets it. Never a placeholder.
        state_id: stateId === "" ? null : Number(stateId),
        grid_owner_id: Number(gridOwnerId),
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
  // Substation lifecycle statuses (substation-registry.md §10, ADR-014) —
  // Planned/Mothballed/Retired remain seeded `operational_status` rows for
  // Equipment Registry's own, independent status model, but are no longer
  // legal for a Substation.
  const substationStatusOptions = referenceData.operationalStatuses.filter((status) =>
    ["UNDER_CONSTRUCTION", "ACTIVE", "DECOMMISSIONED", "ENTERED_IN_ERROR"].includes(status.code),
  );
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
        <dt>GM Zone</dt>
        <dd>{referenceData.gmZonesById.get(substation.gm_zone_id)?.label ?? "—"}</dd>
        <dt>State</dt>
        <dd>
          {substation.state_id === null
            ? "—"
            : (referenceData.statesById.get(substation.state_id)?.label ?? "—")}
        </dd>
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
              <label htmlFor="edit-region">Region</label>
              <br />
              <select
                id="edit-region"
                value={regionId}
                onChange={(e) => setRegionId(e.target.value)}
                required
              >
                <option value="">Select...</option>
                {referenceData.regions.map((region) => (
                  <option key={region.region_id} value={region.region_id}>
                    {region.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="edit-gm-zone">GM Zone</label>
              <br />
              <select
                id="edit-gm-zone"
                value={gmZoneId}
                onChange={(e) => setGmZoneId(e.target.value)}
                required
              >
                <option value="">Select...</option>
                {referenceData.gmZones.map((zone) => (
                  <option key={zone.gm_zone_id} value={zone.gm_zone_id}>
                    {zone.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="edit-state">State (Optional)</label>
              <br />
              <select
                id="edit-state"
                value={stateId}
                onChange={(e) => setStateId(e.target.value)}
              >
                <option value="">None</option>
                {referenceData.states.map((state) => (
                  <option key={state.state_id} value={state.state_id}>
                    {state.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="edit-grid-owner">Grid owner</label>
              <br />
              <select
                id="edit-grid-owner"
                value={gridOwnerId}
                onChange={(e) => setGridOwnerId(e.target.value)}
                required
              >
                <option value="">Select...</option>
                {referenceData.gridOwners.map((owner) => (
                  <option key={owner.grid_owner_id} value={owner.grid_owner_id}>
                    {owner.label}
                  </option>
                ))}
              </select>
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
              {substationStatusOptions.map((status) => (
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
      <label htmlFor="show-entered-in-error-yards">
        <input
          id="show-entered-in-error-yards"
          type="checkbox"
          checked={showEnteredInErrorYards}
          onChange={(e) => setShowEnteredInErrorYards(e.target.checked)}
        />{" "}
        Show entered-in-error switchyards
      </label>
      <ul data-testid="voltage-yards-list">
        {visibleVoltageYards.map((yard) => (
          <VoltageYardRow
            key={yard.voltage_yard_id}
            yard={yard}
            canWrite={canManageVoltageYards}
            onSaved={invalidateVoltageYards}
            statusLabel={
              referenceData.operationalStatusesById.get(yard.operational_status_id)?.label ?? ""
            }
            enteredInErrorStatusId={enteredInErrorStatusId}
          />
        ))}
        {visibleVoltageYards.length === 0 && <li>No switchyards registered yet.</li>}
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

      <h3>Transformers</h3>
      <p>
        Transformers are substation-owned equipment — every transformer installed here connects
        two of this substation&apos;s own switchyards (HV and LV).
      </p>
      <ul data-testid="transformers-list">
        {(transformersQuery.data?.items ?? []).map((transformer) => (
          <li key={transformer.transformer_id}>
            <Link to={`/transformers/${transformer.transformer_id}`}>
              {transformer.generated_short_name}
            </Link>{" "}
            ({transformer.hv_voltage_level_label} ↔ {transformer.lv_voltage_level_label})
          </li>
        ))}
        {transformersQuery.data?.items.length === 0 && <li>No transformers installed here yet.</li>}
      </ul>

      <h3>Engineering Connectivity</h3>
      <p>
        Circuits connected to this substation, derived from the Circuit Registry&apos;s own
        Circuit/CircuitTerminal records — the manually maintained engineering baseline. This is not
        PSS/E-derived operational topology; a future phase will add that as a separate, comparable
        snapshot, never a silent overwrite of this baseline.
      </p>
      <p data-testid="connected-circuits-count">
        Connected Circuits: {connectedCircuitsQuery.data?.total ?? 0}
      </p>
      {(connectedCircuitsQuery.data?.items.length ?? 0) === 0 ? (
        <p>No connected circuits recorded in the engineering registry.</p>
      ) : (
        <table data-testid="engineering-connectivity-table">
          <thead>
            <tr>
              <th>Circuit</th>
              <th>Bay Number</th>
              <th>Voltage Level</th>
              <th>Line Type</th>
              <th>Status</th>
              <th>Other Connected Substations</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {(connectedCircuitsQuery.data?.items ?? []).map((circuit) => {
              const otherSubstations = circuit.circuit_name
                .split("–")
                .map((mnemonic) => mnemonic.trim())
                .filter((mnemonic) => mnemonic !== "" && mnemonic !== substation.mnemonic);
              return (
                <tr key={circuit.circuit_id}>
                  <td>{circuit.circuit_name}</td>
                  <td>{circuit.bay_number}</td>
                  <td>{referenceData.voltageLevelsById.get(circuit.voltage_level_id)?.label}</td>
                  <td>{referenceData.lineTypesById.get(circuit.line_type_id)?.label}</td>
                  <td>
                    {referenceData.operationalStatusesById.get(circuit.operational_status_id)
                      ?.label}
                  </td>
                  <td>{otherSubstations.length > 0 ? otherSubstations.join(", ") : "—"}</td>
                  <td>
                    <Link to={`/circuits/${circuit.circuit_id}`}>View</Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
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
