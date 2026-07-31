import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { Badge } from "../../../components/ui/Badge";
import { Button } from "../../../components/ui/Button";
import { ConfirmActionDialog } from "../../../components/ui/ConfirmActionDialog";
import { DetailSection } from "../../../components/ui/DetailSection";
import { ErrorState } from "../../../components/ui/ErrorState";
import { MetadataList } from "../../../components/ui/MetadataList";
import { PageHeader } from "../../../components/ui/PageHeader";
import { SelectField } from "../../../components/ui/SelectField";
import { TextField } from "../../../components/ui/TextField";
import { tokens } from "../../../theme/tokens";
import { useAuth } from "../../iam/AuthContext";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import type { VoltageYardSummary } from "../../equipment_registry/types";
import { SubstationForm } from "../components/SubstationForm";
import { useChangeStatusMutation, useSubstationAliasesQuery, useSubstationAuditLogQuery, useSubstationQuery, useUpdateSubstationMutation } from "../hooks";
import { allowedTargetStatuses, toneForStatusCode } from "../lifecycle";
import type { SubstationCreate, SubstationUpdate } from "../types";

interface VoltageYardRowProps {
  yard: VoltageYardSummary;
  canWrite: boolean;
  onSaved: () => void;
  statusLabel: string;
  enteredInErrorStatusId: number | undefined;
}

/** One switchyard's editable metadata — RETAINED verbatim from Phase 3
 * (Equipment Registry, ADR-008/ADR-027): out of scope for Phase E to redesign.
 * commissioning_date/latitude/longitude belong to the switchyard, not the
 * parent Substation. "Mark as Entered in Error" / "Restore Voltage Yard" are
 * mutually-exclusive audited lifecycle actions, never a delete/undelete. */
function VoltageYardRow({ yard, canWrite, onSaved, statusLabel, enteredInErrorStatusId }: VoltageYardRowProps) {
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
    onError: (err: unknown) => setError(err instanceof ApiError ? err.message : "Failed to update switchyard."),
  });

  const isEnteredInError = yard.operational_status_id === enteredInErrorStatusId;

  const correctionMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateVoltageYard(yard.voltage_yard_id, {
        operational_status_id: enteredInErrorStatusId,
        change_reason: correctionReason,
      }),
    onSuccess: () => {
      setCorrectionError(null);
      setCorrectionReason("");
      onSaved();
    },
    onError: (err: unknown) => setCorrectionError(err instanceof ApiError ? err.message : "Failed to correct switchyard."),
  });

  const restoreMutation = useMutation({
    mutationFn: () => equipmentRegistryApi.restoreVoltageYard(yard.voltage_yard_id, { change_reason: restoreReason }),
    onSuccess: () => {
      setRestoreError(null);
      setRestoreReason("");
      setRestoreMessage(`${yard.voltage_level_label} switchyard restored to Active.`);
      onSaved();
    },
    onError: (err: unknown) => setRestoreError(err instanceof ApiError ? err.message : "Failed to restore switchyard."),
  });

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
          This switchyard is marked Entered in Error. Restoring it returns it to <strong>Active</strong>. Its audit history is preserved.
        </p>
        <label htmlFor={`yard-restore-reason-${yard.voltage_yard_id}`}>Reason for restoring {yard.voltage_level_label}</label>
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
        {yard.voltage_level_label} ({statusLabel}) — commissioned {yard.commissioning_date ?? "—"}, at {yard.latitude ?? "—"}, {yard.longitude ?? "—"}
      </li>
    );
  }

  return (
    <li>
      {yard.voltage_level_label} ({statusLabel})
      <div>
        <label htmlFor={`yard-commissioning-date-${yard.voltage_yard_id}`}>Commissioning date for {yard.voltage_level_label}</label>
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
        <label htmlFor={`yard-latitude-${yard.voltage_yard_id}`}>Latitude for {yard.voltage_level_label}</label>
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
        <label htmlFor={`yard-longitude-${yard.voltage_yard_id}`}>Longitude for {yard.voltage_level_label}</label>
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
      <button type="button" onClick={() => updateMutation.mutate()} disabled={updateMutation.isPending}>
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
  const id = substationId ?? "";
  const { permissions } = useAuth();
  const canWrite = permissions.has("substation_registry.write");
  const canManageVoltageYards = permissions.has("equipment_registry.write");
  const referenceData = useReferenceData();
  const queryClient = useQueryClient();

  const substationQuery = useSubstationQuery(substationId);
  const aliasesQuery = useSubstationAliasesQuery(substationId);
  const auditLogQuery = useSubstationAuditLogQuery(substationId);

  // --- Retained Equipment Registry sections (verbatim data logic) ---
  const [showEnteredInErrorYards, setShowEnteredInErrorYards] = useState(false);
  const voltageYardsQuery = useQuery({
    queryKey: ["substation", substationId, "voltage-yards"],
    queryFn: () => equipmentRegistryApi.listVoltageYards({ substation_id: id, include_entered_in_error: true }),
    enabled: substationId !== undefined,
  });
  const enteredInErrorStatusId = referenceData.operationalStatuses.find((s) => s.code === "ENTERED_IN_ERROR")?.operational_status_id;
  const visibleVoltageYards = (voltageYardsQuery.data ?? []).filter(
    (yard) => showEnteredInErrorYards || yard.operational_status_id !== enteredInErrorStatusId,
  );

  const transformersQuery = useQuery({
    queryKey: ["substation", substationId, "transformers"],
    queryFn: () => equipmentRegistryApi.listTransformers({ substation_id: id, page_size: 200 }),
    enabled: substationId !== undefined,
  });

  const connectedCircuitsQuery = useQuery({
    queryKey: ["substation", substationId, "circuits"],
    queryFn: () => equipmentRegistryApi.listCircuits({ substation_id: id, page_size: 200 }),
    enabled: substationId !== undefined,
  });

  // --- Substation edit (shared form) ---
  const [editError, setEditError] = useState<string | null>(null);
  const updateMutation = useUpdateSubstationMutation(id);

  function handleEditSubmit(payload: SubstationCreate | SubstationUpdate): void {
    setEditError(null);
    updateMutation.mutate(payload as SubstationUpdate, {
      onError: (err: unknown) => setEditError(err instanceof ApiError ? err.message : "Failed to update substation."),
    });
  }

  // --- Lifecycle status change (confirm dialog offering only legal transitions) ---
  const [statusDialogOpen, setStatusDialogOpen] = useState(false);
  const [targetStatusId, setTargetStatusId] = useState("");
  const [changeReason, setChangeReason] = useState("");
  const [statusError, setStatusError] = useState<string | null>(null);
  const changeStatusMutation = useChangeStatusMutation(id);

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
        substation_id: id,
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
    onError: (err: unknown) => setNewYardError(err instanceof ApiError ? err.message : "Failed to add switchyard."),
  });

  function handleAddVoltageYardSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    addVoltageYardMutation.mutate();
  }

  if (substationQuery.isPending) {
    return <p style={{ fontFamily: tokens.typography.fontFamily, color: tokens.color.textSecondary }}>Loading substation…</p>;
  }
  if (substationQuery.isError || !substationQuery.data) {
    const notFound = substationQuery.error instanceof ApiError && substationQuery.error.status === 404;
    return (
      <div style={{ maxWidth: "720px", margin: "0 auto" }}>
        <ErrorState
          title={notFound ? "Substation not found" : "Couldn't load this substation"}
          message={
            notFound
              ? "This substation record does not exist, or the link is out of date."
              : substationQuery.error instanceof ApiError
                ? substationQuery.error.message
                : "The record could not be reached."
          }
        />
        <p style={{ marginTop: tokens.space[4] }}>
          <Link to="/substations" style={{ color: tokens.color.link, fontFamily: tokens.typography.fontFamily }}>← Back to Substation Registry</Link>
        </p>
      </div>
    );
  }

  const substation = substationQuery.data;
  const currentStatus = referenceData.operationalStatusesById.get(substation.operational_status_id);
  const targetStatusOptions = allowedTargetStatuses(substation.operational_status_id, referenceData.operationalStatuses);
  const usedVoltageLevelIds = new Set((voltageYardsQuery.data ?? []).map((y) => y.voltage_level_id));
  const availableVoltageLevelsForNewYard = referenceData.voltageLevels.filter((level) => !usedVoltageLevelIds.has(level.voltage_level_id));

  const displayOrDash = (value: string | undefined) => (value && value.length > 0 ? value : "—");

  function closeStatusDialog(): void {
    setStatusDialogOpen(false);
    setTargetStatusId("");
    setChangeReason("");
    setStatusError(null);
  }

  function confirmStatusChange(): void {
    setStatusError(null);
    changeStatusMutation.mutate(
      { operational_status_id: Number(targetStatusId), change_reason: changeReason.trim() || null },
      {
        onSuccess: () => closeStatusDialog(),
        onError: (err: unknown) => setStatusError(err instanceof ApiError ? err.message : "Status change was rejected."),
      },
    );
  }

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto" }}>
      <PageHeader
        title={substation.official_name}
        description={
          <span style={{ display: "inline-flex", alignItems: "center", gap: tokens.space[2], flexWrap: "wrap" }}>
            <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>{substation.mnemonic}</span>
            <span>·</span>
            <Badge label={currentStatus?.label ?? String(substation.operational_status_id)} tone={toneForStatusCode(currentStatus?.code)} />
          </span>
        }
        meta={<Link to="/substations" style={{ color: tokens.color.link, textDecoration: "none" }}>← Substation Registry</Link>}
      />

      {/* align-items: start so each summary card sizes to its own content (no
          stretch), avoiding empty space now that the descriptions are gone. */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(min(320px, 100%), 1fr))", gap: tokens.space[4], marginBottom: tokens.space[4], alignItems: "start" }}>
        {/* PSS/E bus correlation is snapshot-scoped and one-to-many
            (TopologyBus.substation_id, per TopologyVersion — ADR-006/ADR-003),
            owned by PSS/E Integration / Network Model. The registry's singular
            psse_bus_number would misrepresent that as a permanent 1:1 identity,
            and this page has no snapshot context — so it is not shown here (see
            substation-registry-frontend.md). No value is inferred or fetched. */}
        <DetailSection title="Identity">
          <MetadataList
            items={[
              { term: "Mnemonic", value: <span style={{ fontVariantNumeric: "tabular-nums", fontWeight: tokens.typography.weight.semibold }}>{substation.mnemonic}</span> },
              { term: "Official name", value: substation.official_name },
            ]}
          />
        </DetailSection>

        <DetailSection title="Engineering Classification">
          <MetadataList
            items={[
              { term: "Region", value: displayOrDash(referenceData.regionsById.get(substation.region_id)?.label) },
              { term: "GM Zone", value: displayOrDash(referenceData.gmZonesById.get(substation.gm_zone_id)?.label) },
              { term: "State", value: substation.state_id === null ? "—" : displayOrDash(referenceData.statesById.get(substation.state_id)?.label) },
              { term: "Grid owner", value: displayOrDash(referenceData.gridOwnersById.get(substation.grid_owner_id)?.label) },
            ]}
          />
        </DetailSection>

        <DetailSection
          title="Lifecycle"
          actions={
            canWrite && targetStatusOptions.length > 0 ? (
              <Button variant="secondary" onClick={() => setStatusDialogOpen(true)}>Change status</Button>
            ) : undefined
          }
        >
          <MetadataList
            items={[
              { term: "Current status", value: <Badge label={currentStatus?.label ?? String(substation.operational_status_id)} tone={toneForStatusCode(currentStatus?.code)} /> },
            ]}
          />
          {canWrite && targetStatusOptions.length === 0 && (
            <p style={mutedSmall}>No status changes are available from the current state.</p>
          )}
        </DetailSection>

        <DetailSection title="Audit & Revision">
          <MetadataList
            items={[
              { term: "Created", value: `${formatDateTime(substation.created_at)} · ${substation.created_by?.display_name ?? substation.created_by?.username ?? "—"}` },
              { term: "Last updated", value: `${formatDateTime(substation.updated_at)} · ${substation.updated_by?.display_name ?? substation.updated_by?.username ?? "—"}` },
            ]}
          />
        </DetailSection>
      </div>

      {canWrite && (
        <div style={{ marginBottom: tokens.space[4] }}>
          <DetailSection title="Edit">
            <SubstationForm mode="edit" referenceData={referenceData} initial={substation} submitting={updateMutation.isPending} error={editError} onSubmit={handleEditSubmit} />
          </DetailSection>
        </div>
      )}

      {/* ---- Retained Equipment Registry sections ---- */}
      <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[4] }}>
        <DetailSection
          title="Switchyards"
          description="The authoritative representation of this substation's voltage level(s) (ADR-009): one row per voltage level. Circuit terminals connect to a specific switchyard, not the substation as a whole."
        >
          <label htmlFor="show-entered-in-error-yards" style={{ display: "inline-flex", alignItems: "center", gap: tokens.space[2], fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small }}>
            <input id="show-entered-in-error-yards" type="checkbox" checked={showEnteredInErrorYards} onChange={(e) => setShowEnteredInErrorYards(e.target.checked)} /> Show entered-in-error switchyards
          </label>
          <ul data-testid="voltage-yards-list">
            {visibleVoltageYards.map((yard) => (
              <VoltageYardRow
                key={yard.voltage_yard_id}
                yard={yard}
                canWrite={canManageVoltageYards}
                onSaved={invalidateVoltageYards}
                statusLabel={referenceData.operationalStatusesById.get(yard.operational_status_id)?.label ?? ""}
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
                    <select id="new-yard-voltage-level" aria-label="New switchyard voltage level" value={newYardVoltageLevelId} onChange={(e) => setNewYardVoltageLevelId(e.target.value)} required>
                      <option value="">Select voltage level...</option>
                      {availableVoltageLevelsForNewYard.map((level) => (
                        <option key={level.voltage_level_id} value={level.voltage_level_id}>{level.label}</option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor="new-yard-commissioning-date">New switchyard commissioning date (optional)</label>
                    <br />
                    <input id="new-yard-commissioning-date" aria-label="New switchyard commissioning date" type="date" value={newYardCommissioningDate} onChange={(e) => setNewYardCommissioningDate(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="new-yard-latitude">New switchyard latitude (optional)</label>
                    <br />
                    <input id="new-yard-latitude" aria-label="New switchyard latitude" type="number" step="any" min={-90} max={90} value={newYardLatitude} onChange={(e) => setNewYardLatitude(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="new-yard-longitude">New switchyard longitude (optional)</label>
                    <br />
                    <input id="new-yard-longitude" aria-label="New switchyard longitude" type="number" step="any" min={-180} max={180} value={newYardLongitude} onChange={(e) => setNewYardLongitude(e.target.value)} />
                  </div>
                  <button type="submit" disabled={addVoltageYardMutation.isPending}>Add switchyard</button>
                  {newYardError && <p role="alert">{newYardError}</p>}
                </form>
              ) : (
                <p>This substation already has a switchyard at every known voltage level.</p>
              )}
            </>
          )}
        </DetailSection>

        <DetailSection title="Transformers" description="Transformers are substation-owned equipment — every transformer installed here connects two of this substation's own switchyards (HV and LV).">
          <ul data-testid="transformers-list">
            {(transformersQuery.data?.items ?? []).map((transformer) => (
              <li key={transformer.transformer_id}>
                <Link to={`/transformers/${transformer.transformer_id}`}>{transformer.generated_short_name}</Link> ({transformer.hv_voltage_level_label} ↔ {transformer.lv_voltage_level_label})
              </li>
            ))}
            {transformersQuery.data?.items.length === 0 && <li>No transformers installed here yet.</li>}
          </ul>
        </DetailSection>

        <DetailSection title="Engineering Connectivity" description="Circuits connected to this substation, derived from the Circuit Registry's own Circuit/CircuitTerminal records — the manually maintained engineering baseline, not PSS/E-derived operational topology.">
          <p data-testid="connected-circuits-count" style={{ margin: 0, fontFamily: tokens.typography.fontFamily, fontWeight: tokens.typography.weight.semibold }}>
            Connected Circuits: {connectedCircuitsQuery.data?.total ?? 0}
          </p>
          {(connectedCircuitsQuery.data?.items.length ?? 0) === 0 ? (
            <p>No connected circuits recorded in the engineering registry.</p>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table data-testid="engineering-connectivity-table" style={{ width: "100%", borderCollapse: "collapse", fontFamily: tokens.typography.fontFamily, fontSize: "13px" }}>
                <thead>
                  <tr>
                    <th style={connThStyle}>Circuit</th>
                    <th style={connThStyle}>Bay Number</th>
                    <th style={connThStyle}>Voltage Level</th>
                    <th style={connThStyle}>Line Type</th>
                    <th style={connThStyle}>Status</th>
                    <th style={connThStyle}>Other Connected Substations</th>
                    <th style={connThStyle}></th>
                  </tr>
                </thead>
                <tbody>
                  {(connectedCircuitsQuery.data?.items ?? []).map((circuit) => {
                    const otherSubstations = circuit.circuit_name
                      .split("–")
                      .map((m) => m.trim())
                      .filter((m) => m !== "" && m !== substation.mnemonic);
                    return (
                      <tr key={circuit.circuit_id} style={{ borderTop: `1px solid ${tokens.color.borderDivider}` }}>
                        <td style={connTdStyle}>{circuit.circuit_name}</td>
                        <td style={connTdStyle}>{circuit.bay_number}</td>
                        <td style={connTdStyle}>{referenceData.voltageLevelsById.get(circuit.voltage_level_id)?.label}</td>
                        <td style={connTdStyle}>{referenceData.lineTypesById.get(circuit.line_type_id)?.label}</td>
                        <td style={connTdStyle}>{referenceData.operationalStatusesById.get(circuit.operational_status_id)?.label}</td>
                        <td style={connTdStyle}>{otherSubstations.length > 0 ? otherSubstations.join(", ") : "—"}</td>
                        <td style={connTdStyle}><Link to={`/circuits/${circuit.circuit_id}`}>View</Link></td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </DetailSection>

        <DetailSection title="Alias history" description="Retired mnemonics preserved when this substation was renamed (identity history is never overwritten).">
          <ul>
            {(aliasesQuery.data ?? []).map((alias) => (
              <li key={alias.alias_id}>
                {alias.alias_mnemonic ?? alias.alias_name} (valid {formatDateTime(alias.valid_from)} – {alias.valid_to ? formatDateTime(alias.valid_to) : "present"})
              </li>
            ))}
            {aliasesQuery.data?.length === 0 && <li>No prior aliases.</li>}
          </ul>
        </DetailSection>

        <DetailSection title="Audit log" description="Field-level change history for this record.">
          <ul>
            {(auditLogQuery.data?.items ?? []).map((entry) => (
              <li key={entry.log_id}>
                {entry.field_name}: {entry.old_value ?? "—"} → {entry.new_value ?? "—"} ({entry.changed_by?.display_name ?? entry.changed_by?.username ?? "unknown"}, {formatDateTime(entry.changed_at)})
                {entry.change_reason ? ` — ${entry.change_reason}` : ""}
              </li>
            ))}
            {auditLogQuery.data?.items.length === 0 && <li>No changes recorded yet.</li>}
          </ul>
        </DetailSection>
      </div>

      <ConfirmActionDialog
        open={statusDialogOpen}
        title="Change substation status"
        description={
          <>
            Changing the operational status is an audited engineering action that follows the defined
            lifecycle transitions. The current status is <strong>{currentStatus?.label}</strong>.
          </>
        }
        confirmLabel="Change status"
        confirmTone={targetStatusOptions.find((s) => s.operational_status_id === Number(targetStatusId))?.code === "ENTERED_IN_ERROR" ? "danger" : "primary"}
        error={statusError}
        pending={changeStatusMutation.isPending}
        confirmDisabled={targetStatusId === ""}
        onCancel={closeStatusDialog}
        onConfirm={confirmStatusChange}
      >
        <SelectField label="New status" value={targetStatusId} onChange={(e) => setTargetStatusId(e.target.value)} required>
          <option value="">Select new status…</option>
          {targetStatusOptions.map((status) => (
            <option key={status.operational_status_id} value={status.operational_status_id}>{status.label}</option>
          ))}
        </SelectField>
        <TextField label="Change reason" placeholder="Recorded in the audit log (optional)" value={changeReason} onChange={(e) => setChangeReason(e.target.value)} />
      </ConfirmActionDialog>
    </div>
  );
}

function formatDateTime(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

const mutedSmall = {
  margin: 0,
  fontFamily: tokens.typography.fontFamily,
  fontSize: tokens.typography.size.small,
  color: tokens.color.textSecondary,
} as const;

const connThStyle = {
  padding: "8px 12px",
  textAlign: "left",
  fontSize: "10.5px",
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  color: tokens.color.textSecondary,
  fontWeight: tokens.typography.weight.bold,
  background: tokens.color.surfaceSubtle,
  whiteSpace: "nowrap",
} as const;

const connTdStyle = {
  padding: "8px 12px",
  color: tokens.color.textPrimary,
  whiteSpace: "nowrap",
} as const;
