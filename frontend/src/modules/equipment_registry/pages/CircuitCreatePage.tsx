import { useQuery, useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { equipmentRegistryApi } from "../api";
import type { CircuitTerminalCreate } from "../types";

interface TerminalRow {
  voltageYardId: string;
  breakerNumber: string;
  commissioningDate: string;
}

const MINIMUM_TERMINALS = 2;

function emptyTerminalRow(): TerminalRow {
  return { voltageYardId: "", breakerNumber: "", commissioningDate: "" };
}

export function CircuitCreatePage() {
  const navigate = useNavigate();
  const referenceData = useReferenceData();

  // A circuit terminal connects to a switchyard (SubstationVoltageYard —
  // internal model name unchanged, ADR-008 addendum), not a substation
  // directly (equipment-registry-module.md §7.5a; ADR-008) — a multi-voltage
  // substation (e.g. PKLG with both a 275kV and a 132kV switchyard) offers
  // one option per switchyard, so the two are independently selectable.
  const voltageYardsQuery = useQuery({
    queryKey: ["voltage-yards", "all-for-circuit-terminal-selection"],
    queryFn: () => equipmentRegistryApi.listVoltageYards(),
  });

  const [bayNumber, setBayNumber] = useState("");
  const [voltageLevelId, setVoltageLevelId] = useState("");
  const [lineTypeId, setLineTypeId] = useState("");
  const [operationalStatusId, setOperationalStatusId] = useState("");
  const [isInterconnector, setIsInterconnector] = useState(false);
  const [remarks, setRemarks] = useState("");
  const [terminals, setTerminals] = useState<TerminalRow[]>([
    emptyTerminalRow(),
    emptyTerminalRow(),
  ]);
  const [error, setError] = useState<string | null>(null);

  function updateTerminal(index: number, field: keyof TerminalRow, value: string): void {
    setTerminals((rows) => rows.map((row, i) => (i === index ? { ...row, [field]: value } : row)));
  }

  function addTerminalRow(): void {
    setTerminals((rows) => [...rows, emptyTerminalRow()]);
  }

  function removeTerminalRow(index: number): void {
    setTerminals((rows) => rows.filter((_, i) => i !== index));
  }

  const createMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.createCircuit({
        bay_number: bayNumber,
        voltage_level_id: Number(voltageLevelId),
        line_type_id: Number(lineTypeId),
        operational_status_id: Number(operationalStatusId),
        is_interconnector: isInterconnector,
        remarks: remarks || null,
        terminals: terminals.map(
          (row): CircuitTerminalCreate => ({
            voltage_yard_id: row.voltageYardId,
            breaker_number: row.breakerNumber,
            commissioning_date: row.commissioningDate || null,
          }),
        ),
      }),
    onSuccess: (detail) => {
      navigate(`/circuits/${detail.circuit_id}`, { replace: true });
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Failed to create circuit.");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setError(null);
    createMutation.mutate();
  }

  // Create: always starts as Planned or Active
  // (equipment-registry-module.md §8, mirroring Substation Registry's own
  // creation-time rule).
  const initialStatusOptions = referenceData.operationalStatuses.filter((status) =>
    ["PLANNED", "ACTIVE"].includes(status.code),
  );

  const canRemoveTerminals = terminals.length > MINIMUM_TERMINALS;

  // Every terminal's switchyard must match the circuit's own voltage
  // level (equipment-registry-module.md §9 rule 6a; Phase 3 UAT follow-up)
  // — enforced by the backend regardless, but filtering here means a
  // mismatched switchyard is never selectable in the first place.
  const availableVoltageYardsForLevel = voltageLevelId
    ? (voltageYardsQuery.data ?? []).filter(
        (yard) => String(yard.voltage_level_id) === voltageLevelId,
      )
    : [];

  return (
    <section>
      <h2>Create circuit</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="bay-number">Bay / Circuit No.</label>
          <br />
          <input
            id="bay-number"
            placeholder="e.g. 1, 2, Main"
            value={bayNumber}
            onChange={(e) => setBayNumber(e.target.value)}
            required
            maxLength={20}
          />
        </div>
        <div>
          <label htmlFor="voltage-level">Voltage level</label>
          <br />
          <select
            id="voltage-level"
            value={voltageLevelId}
            onChange={(e) => setVoltageLevelId(e.target.value)}
            required
          >
            <option value="">Select...</option>
            {referenceData.voltageLevels.map((level) => (
              <option key={level.voltage_level_id} value={level.voltage_level_id}>
                {level.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="line-type">Line type</label>
          <br />
          <select
            id="line-type"
            value={lineTypeId}
            onChange={(e) => setLineTypeId(e.target.value)}
            required
          >
            <option value="">Select...</option>
            {referenceData.lineTypes.map((type) => (
              <option key={type.line_type_id} value={type.line_type_id}>
                {type.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="operational-status">Initial status</label>
          <br />
          <select
            id="operational-status"
            value={operationalStatusId}
            onChange={(e) => setOperationalStatusId(e.target.value)}
            required
          >
            <option value="">Select...</option>
            {initialStatusOptions.map((status) => (
              <option key={status.operational_status_id} value={status.operational_status_id}>
                {status.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="is-interconnector">
            <input
              id="is-interconnector"
              type="checkbox"
              checked={isInterconnector}
              onChange={(e) => setIsInterconnector(e.target.checked)}
            />{" "}
            Interconnector
          </label>
        </div>
        <div>
          <label htmlFor="remarks">Remarks</label>
          <br />
          <textarea id="remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>

        <h3>Terminals</h3>
        <p>
          A circuit must have at least two terminals — one per switchyard it connects to. Add a
          third or more to represent a tee-off. Only switchyards at the circuit's own voltage
          level, selected above, are offered — every terminal of a circuit must connect at the
          circuit's own voltage level.
        </p>
        {voltageYardsQuery.isError && (
          <p role="alert">Failed to load switchyards. Add one from a substation's detail page.</p>
        )}
        {voltageLevelId === "" && (
          <p>Select a voltage level above to see the matching switchyards.</p>
        )}
        {voltageLevelId !== "" && availableVoltageYardsForLevel.length === 0 && (
          <p>
            No suitable switchyard exists at this voltage level. Please add the required
            switchyard from the Substation Registry.
          </p>
        )}
        {terminals.map((row, index) => (
          <fieldset key={index} style={{ marginBottom: "0.75rem" }}>
            <legend>Terminal {index + 1}</legend>
            <div>
              <label htmlFor={`terminal-voltage-yard-${index}`}>Switchyard</label>
              <br />
              <select
                id={`terminal-voltage-yard-${index}`}
                value={row.voltageYardId}
                onChange={(e) => updateTerminal(index, "voltageYardId", e.target.value)}
                required
                disabled={voltageLevelId === ""}
              >
                <option value="">Select...</option>
                {availableVoltageYardsForLevel.map((yard) => (
                  <option key={yard.voltage_yard_id} value={yard.voltage_yard_id}>
                    {yard.display_label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label htmlFor={`terminal-breaker-${index}`}>Breaker number</label>
              <br />
              <input
                id={`terminal-breaker-${index}`}
                placeholder="e.g. L25"
                value={row.breakerNumber}
                onChange={(e) => updateTerminal(index, "breakerNumber", e.target.value)}
                required
                maxLength={20}
              />
            </div>
            <div>
              <label htmlFor={`terminal-commissioning-date-${index}`}>
                Commissioning date (optional)
              </label>
              <br />
              <input
                id={`terminal-commissioning-date-${index}`}
                type="date"
                value={row.commissioningDate}
                onChange={(e) => updateTerminal(index, "commissioningDate", e.target.value)}
              />
            </div>
            {canRemoveTerminals && (
              <button type="button" onClick={() => removeTerminalRow(index)}>
                Remove terminal
              </button>
            )}
          </fieldset>
        ))}
        <button type="button" onClick={addTerminalRow}>
          Add another terminal
        </button>

        {error && <p role="alert">{error}</p>}
        <div style={{ marginTop: "1rem" }}>
          <button type="submit" disabled={createMutation.isPending}>
            Create circuit
          </button>
        </div>
      </form>
    </section>
  );
}
