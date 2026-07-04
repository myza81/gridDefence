import { useQuery, useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { referenceDataApi } from "../../../reference_data/api";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { substationRegistryApi } from "../../substation_registry/api";
import { equipmentRegistryApi } from "../api";
import { suggestBreakerNumber } from "../transformerBreakerSuggestion";

export function TransformerCreatePage() {
  const navigate = useNavigate();
  const referenceData = useReferenceData();

  // Substation-first workflow (UAT correction): a transformer is
  // substation-owned equipment, never modeled as spanning two substations
  // — the user selects the substation before either switchyard, and both
  // switchyard pickers are filtered to that substation only.
  const substationsQuery = useQuery({
    queryKey: ["substations", "all-for-transformer-substation-selection"],
    queryFn: () => substationRegistryApi.listSubstations({ page_size: 500 }),
  });

  // A transformer terminal connects to a switchyard (SubstationVoltageYard),
  // exactly like a circuit terminal — see equipment-registry-module.md's
  // Transformer Registry section. The backend enforces the HV > LV voltage
  // ordering, the same-switchyard rejection, and the HV/LV-must-belong-to-
  // the-selected-substation rule (Architecture Decision Gate outcome; UAT
  // correction).
  const voltageYardsQuery = useQuery({
    queryKey: ["voltage-yards", "all-for-transformer-terminal-selection"],
    queryFn: () => equipmentRegistryApi.listVoltageYards(),
  });

  // The breaker-number suggestion convention (which pattern applies to
  // which HV/LV voltage-level pair and side) is Core Platform reference
  // data, not a hardcoded frontend table — see transformerBreakerSuggestion.ts.
  const breakerConventionsQuery = useQuery({
    queryKey: ["reference-data", "transformer-breaker-numbering-conventions"],
    queryFn: referenceDataApi.listTransformerBreakerNumberingConventions,
  });

  const [substationId, setSubstationId] = useState("");
  const [transformerNumber, setTransformerNumber] = useState("");
  const [hvSwitchyardId, setHvSwitchyardId] = useState("");
  const [hvBreakerNumber, setHvBreakerNumber] = useState("");
  const [hvBreakerTouched, setHvBreakerTouched] = useState(false);
  const [lvSwitchyardId, setLvSwitchyardId] = useState("");
  const [lvBreakerNumber, setLvBreakerNumber] = useState("");
  const [lvBreakerTouched, setLvBreakerTouched] = useState(false);
  const [capacityMva, setCapacityMva] = useState("");
  const [commissioningDate, setCommissioningDate] = useState("");
  const [operationalStatusId, setOperationalStatusId] = useState("");
  const [transformerType, setTransformerType] = useState("");
  const [manufacturer, setManufacturer] = useState("");
  const [remarks, setRemarks] = useState("");
  const [error, setError] = useState<string | null>(null);

  // A previously-selected switchyard may belong to the substation just
  // replaced — clear both so a stale, now-invalid selection can never be
  // submitted (mirrors CircuitCreatePage's own per-voltage-level reset).
  function handleSubstationChange(nextSubstationId: string): void {
    setSubstationId(nextSubstationId);
    setHvSwitchyardId("");
    setLvSwitchyardId("");
  }

  const voltageYards = voltageYardsQuery.data ?? [];
  const switchyardsAtSubstation = substationId
    ? voltageYards.filter((y) => y.substation_id === substationId)
    : [];
  const hvYard = voltageYards.find((y) => y.voltage_yard_id === hvSwitchyardId);
  const lvYard = voltageYards.find((y) => y.voltage_yard_id === lvSwitchyardId);
  const breakerConventions = breakerConventionsQuery.data ?? [];

  // Breaker-number suggestion (display-only, always overridable — CLAUDE.md
  // A12; never sent as a default the backend validates against). Waits for
  // the transformer number, both switchyards' voltage levels, and the
  // reference-data convention list itself — the pattern depends on the
  // transformation pair (not either voltage alone) and is looked up from
  // `breakerConventions`, never hardcoded here.
  useEffect(() => {
    if (
      hvBreakerTouched ||
      hvYard === undefined ||
      lvYard === undefined ||
      breakerConventionsQuery.isLoading
    ) {
      return;
    }
    const suggestion = suggestBreakerNumber(
      breakerConventions,
      hvYard.voltage_level_id,
      lvYard.voltage_level_id,
      "HV",
      transformerNumber,
    );
    setHvBreakerNumber(suggestion ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hvSwitchyardId, lvSwitchyardId, transformerNumber, breakerConventionsQuery.isLoading]);

  useEffect(() => {
    if (
      lvBreakerTouched ||
      hvYard === undefined ||
      lvYard === undefined ||
      breakerConventionsQuery.isLoading
    ) {
      return;
    }
    const suggestion = suggestBreakerNumber(
      breakerConventions,
      hvYard.voltage_level_id,
      lvYard.voltage_level_id,
      "LV",
      transformerNumber,
    );
    setLvBreakerNumber(suggestion ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hvSwitchyardId, lvSwitchyardId, transformerNumber, breakerConventionsQuery.isLoading]);

  const createMutation = useMutation({
    mutationFn: () =>
      equipmentRegistryApi.createTransformer({
        substation_id: substationId,
        transformer_number: transformerNumber,
        hv_switchyard_id: hvSwitchyardId,
        hv_breaker_number: hvBreakerNumber,
        lv_switchyard_id: lvSwitchyardId,
        lv_breaker_number: lvBreakerNumber,
        capacity_mva: capacityMva ? Number(capacityMva) : null,
        commissioning_date: commissioningDate || null,
        operational_status_id: Number(operationalStatusId),
        transformer_type: transformerType || null,
        manufacturer: manufacturer || null,
        remarks: remarks || null,
      }),
    onSuccess: (detail) => {
      navigate(`/transformers/${detail.transformer_id}`, { replace: true });
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Failed to create transformer.");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setError(null);
    createMutation.mutate();
  }

  // Create: always starts as Planned or Active, mirroring Circuit's own
  // creation-time rule (equipment-registry-module.md §8).
  const initialStatusOptions = referenceData.operationalStatuses.filter((status) =>
    ["PLANNED", "ACTIVE"].includes(status.code),
  );

  return (
    <section>
      <h2>Create transformer</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="substation">Substation</label>
          <br />
          <select
            id="substation"
            value={substationId}
            onChange={(e) => handleSubstationChange(e.target.value)}
            required
          >
            <option value="">Select...</option>
            {(substationsQuery.data?.items ?? []).map((substation) => (
              <option key={substation.substation_id} value={substation.substation_id}>
                {substation.mnemonic} — {substation.official_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="transformer-number">Bay / Transformer Number</label>
          <br />
          <input
            id="transformer-number"
            placeholder="e.g. 1, 2, Main"
            value={transformerNumber}
            onChange={(e) => setTransformerNumber(e.target.value)}
            required
            maxLength={20}
          />
        </div>

        {substationsQuery.isError && <p role="alert">Failed to load substations.</p>}
        {voltageYardsQuery.isError && (
          <p role="alert">Failed to load switchyards. Add one from a substation's detail page.</p>
        )}
        {breakerConventionsQuery.isError && (
          <p role="alert">
            Failed to load breaker-number suggestions — you may still enter breaker numbers
            manually.
          </p>
        )}
        {substationId === "" && (
          <p>Select a substation above to see its switchyards.</p>
        )}
        {substationId !== "" && switchyardsAtSubstation.length === 0 && (
          <p>
            This substation has no switchyards yet. Please add the required switchyards from the
            Substation Registry.
          </p>
        )}

        <fieldset style={{ marginTop: "1rem" }}>
          <legend>HV side</legend>
          <div>
            <label htmlFor="hv-switchyard">HV switchyard</label>
            <br />
            <select
              id="hv-switchyard"
              value={hvSwitchyardId}
              onChange={(e) => setHvSwitchyardId(e.target.value)}
              required
              disabled={substationId === ""}
            >
              <option value="">Select...</option>
              {switchyardsAtSubstation.map((yard) => (
                <option key={yard.voltage_yard_id} value={yard.voltage_yard_id}>
                  {yard.display_label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="hv-breaker">HV breaker number</label>
            <br />
            <input
              id="hv-breaker"
              placeholder="e.g. H20"
              value={hvBreakerNumber}
              onChange={(e) => {
                setHvBreakerTouched(true);
                setHvBreakerNumber(e.target.value);
              }}
              required
              maxLength={20}
            />
          </div>
        </fieldset>

        <fieldset style={{ marginTop: "1rem" }}>
          <legend>LV side</legend>
          <div>
            <label htmlFor="lv-switchyard">LV switchyard</label>
            <br />
            <select
              id="lv-switchyard"
              value={lvSwitchyardId}
              onChange={(e) => setLvSwitchyardId(e.target.value)}
              required
              disabled={substationId === ""}
            >
              <option value="">Select...</option>
              {switchyardsAtSubstation.map((yard) => (
                <option key={yard.voltage_yard_id} value={yard.voltage_yard_id}>
                  {yard.display_label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="lv-breaker">LV breaker number</label>
            <br />
            <input
              id="lv-breaker"
              placeholder="e.g. 210"
              value={lvBreakerNumber}
              onChange={(e) => {
                setLvBreakerTouched(true);
                setLvBreakerNumber(e.target.value);
              }}
              required
              maxLength={20}
            />
          </div>
        </fieldset>

        <div style={{ marginTop: "1rem" }}>
          <label htmlFor="capacity-mva">Capacity (MVA)</label>
          <br />
          <input
            id="capacity-mva"
            type="number"
            step="0.01"
            min="0"
            value={capacityMva}
            onChange={(e) => setCapacityMva(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="commissioning-date">Commissioning date (optional)</label>
          <br />
          <input
            id="commissioning-date"
            type="date"
            value={commissioningDate}
            onChange={(e) => setCommissioningDate(e.target.value)}
          />
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
          <label htmlFor="transformer-type">Transformer type (optional)</label>
          <br />
          <input
            id="transformer-type"
            value={transformerType}
            onChange={(e) => setTransformerType(e.target.value)}
            maxLength={50}
          />
        </div>
        <div>
          <label htmlFor="manufacturer">Manufacturer (optional)</label>
          <br />
          <input
            id="manufacturer"
            value={manufacturer}
            onChange={(e) => setManufacturer(e.target.value)}
            maxLength={100}
          />
        </div>
        <div>
          <label htmlFor="remarks">Remarks</label>
          <br />
          <textarea id="remarks" value={remarks} onChange={(e) => setRemarks(e.target.value)} />
        </div>

        {error && <p role="alert">{error}</p>}
        <div style={{ marginTop: "1rem" }}>
          <button type="submit" disabled={createMutation.isPending}>
            Create transformer
          </button>
        </div>
      </form>
    </section>
  );
}
