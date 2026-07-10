import { useMutation, useQuery } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import { networkModelApi } from "../../network_model/api";
import { substationRegistryApi } from "../../substation_registry/api";
import { automaticLoadSheddingFunctionalityApi } from "../api";
import { formatTerminalIdentity } from "../displayHelpers";
import type { TargetType } from "../types";

/** Create page (module document §12/§17 UI requirements). Bay Terminal
 * selection is a cascading picker — Substation, then Terminal Type
 * (Circuit/Transformer), then the specific Bay — reusing Network Model's
 * existing `getSubstationEquipment` read view and Equipment Registry's
 * `getTransformer` detail (for HV/LV terminal ids), rather than
 * duplicating any Equipment Registry data (module document §4). */
export function FunctionalityCreatePage() {
  const navigate = useNavigate();

  const [substationId, setSubstationId] = useState("");
  const [targetType, setTargetType] = useState<TargetType>("CIRCUIT_TERMINAL");
  const [circuitTerminalId, setCircuitTerminalId] = useState("");
  const [transformerId, setTransformerId] = useState("");
  const [transformerTerminalId, setTransformerTerminalId] = useState("");
  const [uflsFunction, setUflsFunction] = useState(false);
  const [uvlsFunction, setUvlsFunction] = useState(false);
  const [relayMake, setRelayMake] = useState("");
  const [relayModel, setRelayModel] = useState("");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);

  const substationsQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", "create", "substation-options"],
    queryFn: () => substationRegistryApi.listSubstations({ page_size: 500 }),
  });

  const equipmentQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", "create", "equipment", substationId],
    queryFn: () => networkModelApi.getSubstationEquipment(substationId),
    enabled: substationId !== "",
  });

  const transformerDetailQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", "create", "transformer", transformerId],
    queryFn: () => equipmentRegistryApi.getTransformer(transformerId),
    enabled: transformerId !== "",
  });

  const createMutation = useMutation({
    mutationFn: () =>
      automaticLoadSheddingFunctionalityApi.create({
        target_type: targetType,
        circuit_terminal_id: targetType === "CIRCUIT_TERMINAL" ? circuitTerminalId : null,
        transformer_terminal_id:
          targetType === "TRANSFORMER_TERMINAL" ? transformerTerminalId : null,
        ufls_function: uflsFunction,
        uvls_function: uvlsFunction,
        relay_make: relayMake || null,
        relay_model: relayModel || null,
        remarks: remarks || null,
      }),
    onSuccess: (detail) => {
      navigate(`/automatic-load-shedding-functionality/${detail.id}`, { replace: true });
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Failed to create functionality record."),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setError(null);
    createMutation.mutate();
  }

  const selectedTerminalId =
    targetType === "CIRCUIT_TERMINAL" ? circuitTerminalId : transformerTerminalId;
  const canSubmit =
    selectedTerminalId !== "" && (uflsFunction || uvlsFunction) && !createMutation.isPending;

  return (
    <section>
      <h2>New Automatic Load Shedding Functionality Record</h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="alsf-substation">Substation</label>
          <br />
          <select
            id="alsf-substation"
            value={substationId}
            onChange={(e) => {
              setSubstationId(e.target.value);
              setCircuitTerminalId("");
              setTransformerId("");
              setTransformerTerminalId("");
            }}
            required
          >
            <option value="">Select...</option>
            {substationsQuery.data?.items.map((substation) => (
              <option key={substation.substation_id} value={substation.substation_id}>
                {substation.mnemonic} — {substation.official_name}
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="alsf-target-type">Terminal (Bay) Type</label>
          <br />
          <select
            id="alsf-target-type"
            value={targetType}
            onChange={(e) => {
              setTargetType(e.target.value as TargetType);
              setCircuitTerminalId("");
              setTransformerId("");
              setTransformerTerminalId("");
            }}
          >
            <option value="CIRCUIT_TERMINAL">Circuit Terminal (Line Bay)</option>
            <option value="TRANSFORMER_TERMINAL">Transformer Terminal (Transformer Bay)</option>
          </select>
        </div>

        {targetType === "CIRCUIT_TERMINAL" && (
          <div style={{ marginBottom: "0.75rem" }}>
            <label htmlFor="alsf-circuit-terminal">Line Bay</label>
            <br />
            <select
              id="alsf-circuit-terminal"
              value={circuitTerminalId}
              onChange={(e) => setCircuitTerminalId(e.target.value)}
              disabled={substationId === ""}
              required
            >
              <option value="">Select...</option>
              {equipmentQuery.data?.line_bays.map((bay) => (
                <option key={bay.circuit_terminal_id} value={bay.circuit_terminal_id}>
                  {formatTerminalIdentity(
                    equipmentQuery.data?.substation_mnemonic ?? "",
                    bay.voltage_level_label,
                    `Line ${bay.circuit_name} ${bay.circuit_bay_number}`,
                  )}
                </option>
              ))}
            </select>
            {substationId !== "" && equipmentQuery.data?.line_bays.length === 0 && (
              <p>No line bays registered at this substation.</p>
            )}
          </div>
        )}

        {targetType === "TRANSFORMER_TERMINAL" && (
          <>
            <div style={{ marginBottom: "0.75rem" }}>
              <label htmlFor="alsf-transformer">Transformer</label>
              <br />
              <select
                id="alsf-transformer"
                value={transformerId}
                onChange={(e) => {
                  setTransformerId(e.target.value);
                  setTransformerTerminalId("");
                }}
                disabled={substationId === ""}
                required
              >
                <option value="">Select...</option>
                {equipmentQuery.data?.transformer_bays.map((bay) => (
                  <option key={bay.transformer_id} value={bay.transformer_id}>
                    {formatTerminalIdentity(
                      equipmentQuery.data?.substation_mnemonic ?? "",
                      bay.hv_voltage_level_label,
                      `Transformer ${bay.generated_short_name}`,
                    )}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ marginBottom: "0.75rem" }}>
              <label htmlFor="alsf-transformer-terminal">Transformer Bay (Winding Side)</label>
              <br />
              <select
                id="alsf-transformer-terminal"
                value={transformerTerminalId}
                onChange={(e) => setTransformerTerminalId(e.target.value)}
                disabled={transformerId === ""}
                required
              >
                <option value="">Select...</option>
                {transformerDetailQuery.data?.terminals.map((terminal) => (
                  <option
                    key={terminal.transformer_terminal_id}
                    value={terminal.transformer_terminal_id}
                  >
                    {formatTerminalIdentity(
                      terminal.substation_mnemonic,
                      terminal.voltage_level_label,
                      `Transformer ${transformerDetailQuery.data?.generated_short_name} (${terminal.side})`,
                    )}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}

        <div style={{ marginBottom: "0.75rem" }}>
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
          {!uflsFunction && !uvlsFunction && <p>At least one function must be selected.</p>}
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="alsf-relay-make">Relay make (optional)</label>
          <br />
          <input
            id="alsf-relay-make"
            value={relayMake}
            onChange={(e) => setRelayMake(e.target.value)}
            maxLength={100}
          />
        </div>
        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="alsf-relay-model">Relay model (optional)</label>
          <br />
          <input
            id="alsf-relay-model"
            value={relayModel}
            onChange={(e) => setRelayModel(e.target.value)}
            maxLength={100}
          />
        </div>
        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="alsf-remarks">Remarks</label>
          <br />
          <textarea id="alsf-remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>

        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={!canSubmit}>
          {createMutation.isPending ? "Creating..." : "Create"}
        </button>
      </form>
    </section>
  );
}
