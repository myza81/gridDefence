import { useMutation, useQuery } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { equipmentRegistryApi } from "../../equipment_registry/api";
import { sensitiveCustomerRegistryApi } from "../api";
import { TerminalMultiSelect } from "../components/TerminalMultiSelect";

/** Create page (implementation spec §14, Increment 8; ADR-013 UAT change
 * request). Transformer Terminal selection is a flat, searchable
 * multi-select sourced from every Transformer Terminal across every
 * substation (`TerminalMultiSelect`) — no cascading Substation ->
 * Transformer picker, and no separate Transformer step, since each
 * option's own label already carries full engineering context. A facility
 * may be associated with zero, one, or many currently active Transformer
 * Terminals — this is not alternate-supply modelling, it is the
 * authoritative record of all current supply points. The terminal
 * association remains optional overall — a facility may be registered
 * before any supply point is confirmed (module document §7, §9 rule 5). */
export function FacilityCreatePage() {
  const navigate = useNavigate();

  const [name, setName] = useState("");
  const [facilitySectorId, setFacilitySectorId] = useState("");
  const [sensitivityClassificationId, setSensitivityClassificationId] = useState("");
  const [transformerTerminalIds, setTransformerTerminalIds] = useState<string[]>([]);
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);

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

  const createMutation = useMutation({
    mutationFn: () =>
      sensitiveCustomerRegistryApi.createFacility({
        name,
        facility_sector_id: Number(facilitySectorId),
        sensitivity_classification_id: Number(sensitivityClassificationId),
        transformer_terminal_ids: transformerTerminalIds,
        remarks: remarks || null,
      }),
    onSuccess: (detail) => {
      navigate(`/sensitive-customer-registry/${detail.id}`, { replace: true });
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Failed to create sensitive facility record."),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setError(null);
    createMutation.mutate();
  }

  const canSubmit =
    name.trim() !== "" &&
    facilitySectorId !== "" &&
    sensitivityClassificationId !== "" &&
    !createMutation.isPending;

  return (
    <section>
      <h2>New Sensitive Facility</h2>

      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="scr-name">Facility Name</label>
          <br />
          <input
            id="scr-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={255}
            required
          />
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="scr-sector">Facility Sector</label>
          <br />
          <select
            id="scr-sector"
            value={facilitySectorId}
            onChange={(e) => setFacilitySectorId(e.target.value)}
            required
          >
            <option value="">Select...</option>
            {sectorsQuery.data
              ?.filter((s) => s.is_active)
              .map((sector) => (
                <option key={sector.id} value={sector.id}>
                  {sector.label}
                </option>
              ))}
          </select>
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="scr-classification">Sensitivity Classification</label>
          <br />
          <select
            id="scr-classification"
            value={sensitivityClassificationId}
            onChange={(e) => setSensitivityClassificationId(e.target.value)}
            required
          >
            <option value="">Select...</option>
            {classificationsQuery.data
              ?.filter((c) => c.is_active)
              .map((classification) => (
                <option key={classification.id} value={classification.id}>
                  {classification.label}
                </option>
              ))}
          </select>
        </div>

        <p>
          Transformer Terminal association (optional — a facility may be registered before any
          supply point is confirmed, and may be associated with more than one currently active
          Transformer Terminal).
        </p>

        <div style={{ marginBottom: "0.75rem" }}>
          <TerminalMultiSelect
            identities={terminalIdentitiesQuery.data ?? []}
            selectedIds={transformerTerminalIds}
            onChange={setTransformerTerminalIds}
            isLoading={terminalIdentitiesQuery.isLoading}
          />
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="scr-remarks">Remarks</label>
          <br />
          <textarea id="scr-remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>

        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={!canSubmit}>
          {createMutation.isPending ? "Creating..." : "Create"}
        </button>
      </form>
    </section>
  );
}
