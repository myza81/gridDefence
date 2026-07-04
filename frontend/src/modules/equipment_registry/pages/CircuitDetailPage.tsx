import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../api";
import type { CircuitTerminalSummary } from "../types";

interface TerminalEditRowProps {
  circuitId: string;
  terminal: CircuitTerminalSummary;
  canWrite: boolean;
  onSaved: () => void;
  statusLabel: string;
  enteredInErrorStatusId: number | undefined;
}

/** One editable terminal row — breaker number and commissioning date are
 * editable after creation (Phase 3 UAT must-fix items 1–2); the switchyard
 * a terminal connects to is not (out of this fix package's scope).
 *
 * "Mark as Entered in Error" (deletion/correction policy, Phase 3
 * follow-up) corrects a mistakenly-added terminal — never a delete
 * button, since no hard delete exists for engineering registry records
 * (CLAUDE.md §11.6). Never blocked here, even if it would leave the
 * circuit with fewer than two active terminals — that completeness rule
 * is enforced instead when the circuit tries to (re)enter Active. Hidden
 * once the terminal is already corrected. */
function TerminalEditRow({
  circuitId,
  terminal,
  canWrite,
  onSaved,
  statusLabel,
  enteredInErrorStatusId,
}: TerminalEditRowProps) {
  const [breakerNumber, setBreakerNumber] = useState(terminal.breaker_number);
  const [commissioningDate, setCommissioningDate] = useState(terminal.commissioning_date ?? "");
  const [error, setError] = useState<string | null>(null);
  const [correctionError, setCorrectionError] = useState<string | null>(null);

  useEffect(() => {
    setBreakerNumber(terminal.breaker_number);
    setCommissioningDate(terminal.commissioning_date ?? "");
  }, [terminal.breaker_number, terminal.commissioning_date]);

  const updateMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateTerminal(circuitId, terminal.circuit_terminal_id, {
        breaker_number: breakerNumber,
        commissioning_date: commissioningDate || null,
      }),
    onSuccess: () => {
      setError(null);
      onSaved();
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Failed to update terminal."),
  });

  const isEnteredInError = terminal.operational_status_id === enteredInErrorStatusId;

  const correctionMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateTerminal(circuitId, terminal.circuit_terminal_id, {
        operational_status_id: enteredInErrorStatusId,
      }),
    onSuccess: () => {
      setCorrectionError(null);
      onSaved();
    },
    onError: (err: unknown) =>
      setCorrectionError(
        err instanceof ApiError ? err.message : "Failed to correct terminal.",
      ),
  });

  return (
    <tr>
      <td>
        {terminal.substation_mnemonic} — {terminal.voltage_level_label} (
        {terminal.substation_official_name})
      </td>
      <td>
        {canWrite ? (
          <input
            aria-label={`Breaker number for ${terminal.substation_mnemonic} — ${terminal.voltage_level_label}`}
            value={breakerNumber}
            onChange={(e) => setBreakerNumber(e.target.value)}
            maxLength={20}
          />
        ) : (
          terminal.breaker_number
        )}
      </td>
      <td>
        {canWrite ? (
          <input
            aria-label={`Commissioning date for ${terminal.substation_mnemonic} — ${terminal.voltage_level_label}`}
            type="date"
            value={commissioningDate}
            onChange={(e) => setCommissioningDate(e.target.value)}
          />
        ) : (
          (terminal.commissioning_date ?? "—")
        )}
      </td>
      <td>{statusLabel}</td>
      {canWrite && (
        <td>
          <button
            type="button"
            onClick={() => updateMutation.mutate()}
            disabled={updateMutation.isPending}
          >
            Save
          </button>
          {error && <p role="alert">{error}</p>}
          {!isEnteredInError && enteredInErrorStatusId !== undefined && (
            <>
              <button
                type="button"
                onClick={() => correctionMutation.mutate()}
                disabled={correctionMutation.isPending}
              >
                Mark as Entered in Error
              </button>
              {correctionError && <p role="alert">{correctionError}</p>}
            </>
          )}
        </td>
      )}
    </tr>
  );
}

export function CircuitDetailPage() {
  const { circuitId } = useParams<{ circuitId: string }>();
  const { permissions } = useAuth();
  const canWrite = permissions.has("equipment_registry.write");
  const referenceData = useReferenceData();
  const queryClient = useQueryClient();
  const enteredInErrorStatusId = referenceData.operationalStatuses.find(
    (status) => status.code === "ENTERED_IN_ERROR",
  )?.operational_status_id;

  const circuitQuery = useQuery({
    queryKey: ["circuit", circuitId],
    queryFn: () => equipmentRegistryApi.getCircuit(circuitId!),
    enabled: circuitId !== undefined,
  });

  const auditLogQuery = useQuery({
    queryKey: ["circuit", circuitId, "audit-log"],
    queryFn: () => equipmentRegistryApi.listAuditLog(circuitId!),
    enabled: circuitId !== undefined,
  });

  // Switchyards are master topology data owned exclusively by the
  // Substation Registry module (ADR-009 addendum) — this page only
  // consumes existing switchyards for terminal selection, never creates them.
  const voltageYardsQuery = useQuery({
    queryKey: ["voltage-yards", "all-for-circuit-terminal-selection"],
    queryFn: () => equipmentRegistryApi.listVoltageYards(),
    enabled: canWrite,
  });

  const invalidateCircuit = () => {
    void queryClient.invalidateQueries({ queryKey: ["circuit", circuitId] });
  };

  const [bayNumber, setBayNumber] = useState("");
  const [voltageLevelId, setVoltageLevelId] = useState("");
  const [lineTypeId, setLineTypeId] = useState("");
  const [remarks, setRemarks] = useState("");
  const [editError, setEditError] = useState<string | null>(null);

  useEffect(() => {
    if (circuitQuery.data) {
      setBayNumber(circuitQuery.data.bay_number);
      setVoltageLevelId(String(circuitQuery.data.voltage_level_id));
      setLineTypeId(String(circuitQuery.data.line_type_id));
      setRemarks(circuitQuery.data.remarks ?? "");
    }
  }, [circuitQuery.data]);

  const updateMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.updateCircuit(circuitId!, {
        bay_number: bayNumber,
        voltage_level_id: Number(voltageLevelId),
        line_type_id: Number(lineTypeId),
        remarks: remarks || null,
      }),
    onSuccess: () => {
      setEditError(null);
      invalidateCircuit();
    },
    onError: (err: unknown) =>
      setEditError(err instanceof ApiError ? err.message : "Failed to update circuit."),
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
      equipmentRegistryApi.changeStatus(circuitId!, {
        operational_status_id: Number(statusId),
        change_reason: changeReason || null,
      }),
    onSuccess: () => {
      setStatusError(null);
      setChangeReason("");
      invalidateCircuit();
    },
    onError: (err: unknown) =>
      setStatusError(err instanceof ApiError ? err.message : "Status change rejected."),
  });

  function handleStatusSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    statusMutation.mutate();
  }

  const [newTerminalVoltageYardId, setNewTerminalVoltageYardId] = useState("");
  const [newTerminalBreakerNumber, setNewTerminalBreakerNumber] = useState("");
  const [newTerminalCommissioningDate, setNewTerminalCommissioningDate] = useState("");
  const [terminalError, setTerminalError] = useState<string | null>(null);

  const addTerminalMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.addTerminal(circuitId!, {
        voltage_yard_id: newTerminalVoltageYardId,
        breaker_number: newTerminalBreakerNumber,
        commissioning_date: newTerminalCommissioningDate || null,
      }),
    onSuccess: () => {
      setTerminalError(null);
      setNewTerminalVoltageYardId("");
      setNewTerminalBreakerNumber("");
      setNewTerminalCommissioningDate("");
      invalidateCircuit();
    },
    onError: (err: unknown) =>
      setTerminalError(err instanceof ApiError ? err.message : "Failed to add terminal."),
  });

  function handleAddTerminalSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    addTerminalMutation.mutate();
  }

  if (circuitQuery.isLoading) {
    return <p>Loading circuit...</p>;
  }
  if (circuitQuery.isError || !circuitQuery.data) {
    return <p role="alert">Circuit not found.</p>;
  }

  const circuit = circuitQuery.data;
  const usedVoltageYardIds = new Set(circuit.terminals.map((t) => t.voltage_yard_id));
  // Every terminal's switchyard must match the circuit's own voltage
  // level (equipment-registry-module.md §9 rule 6a; Phase 3 UAT follow-up)
  // — filtered here so a mismatched switchyard is never selectable, in
  // addition to the backend's own enforcement of the same rule.
  const availableVoltageYards = (voltageYardsQuery.data ?? []).filter(
    (y) =>
      !usedVoltageYardIds.has(y.voltage_yard_id) && y.voltage_level_id === circuit.voltage_level_id,
  );

  return (
    <section>
      {/* Circuit route/name and bay/circuit number are shown as distinct
          fields, never combined — circuit_name is the canonical route only
          (Phase 3 close-out; equipment-registry-module.md §7.4) and never
          embeds bay_number, so there is nothing to accidentally duplicate. */}
      <h2>Circuit: {circuit.circuit_name}</h2>
      <dl>
        <dt>Bay / Circuit No.</dt>
        <dd>{circuit.bay_number}</dd>
        <dt>Voltage level</dt>
        <dd>{referenceData.voltageLevelsById.get(circuit.voltage_level_id)?.label}</dd>
        <dt>Line type</dt>
        <dd>{referenceData.lineTypesById.get(circuit.line_type_id)?.label}</dd>
        <dt>Status</dt>
        <dd>{referenceData.operationalStatusesById.get(circuit.operational_status_id)?.label}</dd>
        <dt>Interconnector</dt>
        <dd>{circuit.is_interconnector ? "Yes" : "No"}</dd>
        <dt>Created by</dt>
        <dd>{circuit.created_by?.username ?? "—"}</dd>
        <dt>Updated by</dt>
        <dd>{circuit.updated_by?.username ?? "—"}</dd>
      </dl>

      <h3>Terminals</h3>
      <table>
        <thead>
          <tr>
            <th>Substation — switchyard</th>
            <th>Breaker number</th>
            <th>Commissioning date</th>
            <th>Status</th>
            {canWrite && <th></th>}
          </tr>
        </thead>
        <tbody>
          {circuit.terminals.map((terminal) => (
            <TerminalEditRow
              key={terminal.circuit_terminal_id}
              circuitId={circuitId!}
              terminal={terminal}
              canWrite={canWrite}
              onSaved={invalidateCircuit}
              statusLabel={
                referenceData.operationalStatusesById.get(terminal.operational_status_id)
                  ?.label ?? ""
              }
              enteredInErrorStatusId={enteredInErrorStatusId}
            />
          ))}
        </tbody>
      </table>

      {canWrite && (
        <>
          <h3>Add terminal</h3>
          <p>Extends this circuit into a tee-off by adding another switchyard terminal.</p>
          <form onSubmit={handleAddTerminalSubmit}>
            <select
              aria-label="New terminal switchyard"
              value={newTerminalVoltageYardId}
              onChange={(e) => setNewTerminalVoltageYardId(e.target.value)}
              required
            >
              <option value="">Select switchyard...</option>
              {availableVoltageYards.map((yard) => (
                <option key={yard.voltage_yard_id} value={yard.voltage_yard_id}>
                  {yard.display_label}
                </option>
              ))}
            </select>
            <input
              aria-label="New terminal breaker number"
              placeholder="Breaker number"
              value={newTerminalBreakerNumber}
              onChange={(e) => setNewTerminalBreakerNumber(e.target.value)}
              required
              maxLength={20}
            />
            <input
              aria-label="New terminal commissioning date"
              type="date"
              value={newTerminalCommissioningDate}
              onChange={(e) => setNewTerminalCommissioningDate(e.target.value)}
            />
            <button type="submit" disabled={addTerminalMutation.isPending}>
              Add terminal
            </button>
            {availableVoltageYards.length === 0 && (
              <p>
                No suitable switchyard exists for this circuit. Please add the required
                switchyard from the Substation Registry.
              </p>
            )}
            {terminalError && <p role="alert">{terminalError}</p>}
          </form>

          <h3>Edit</h3>
          <form onSubmit={handleEditSubmit}>
            <div>
              <label htmlFor="edit-bay-number">Bay / Circuit No.</label>
              <br />
              <input
                id="edit-bay-number"
                value={bayNumber}
                onChange={(e) => setBayNumber(e.target.value)}
                maxLength={20}
              />
            </div>
            <div>
              <label htmlFor="edit-voltage-level">Voltage level</label>
              <br />
              <select
                id="edit-voltage-level"
                value={voltageLevelId}
                onChange={(e) => setVoltageLevelId(e.target.value)}
              >
                {referenceData.voltageLevels.map((level) => (
                  <option key={level.voltage_level_id} value={level.voltage_level_id}>
                    {level.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor="edit-line-type">Line type</label>
              <br />
              <select
                id="edit-line-type"
                value={lineTypeId}
                onChange={(e) => setLineTypeId(e.target.value)}
              >
                {referenceData.lineTypes.map((type) => (
                  <option key={type.line_type_id} value={type.line_type_id}>
                    {type.label}
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
