import { useMutation } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useReferenceData } from "../../../reference_data/useReferenceData";
import { substationRegistryApi } from "../api";

export function SubstationCreatePage() {
  const navigate = useNavigate();
  const referenceData = useReferenceData();

  const [mnemonic, setMnemonic] = useState("");
  const [officialName, setOfficialName] = useState("");
  const [regionId, setRegionId] = useState("");
  const [stateId, setStateId] = useState("");
  const [gridOwnerId, setGridOwnerId] = useState("");
  const [operationalStatusId, setOperationalStatusId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      substationRegistryApi.createSubstation({
        mnemonic,
        official_name: officialName,
        region_id: Number(regionId),
        state_id: Number(stateId),
        grid_owner_id: Number(gridOwnerId),
        operational_status_id: Number(operationalStatusId),
      }),
    onSuccess: (detail) => {
      navigate(`/substations/${detail.substation_id}`, { replace: true });
    },
    onError: (err: unknown) => {
      setError(err instanceof ApiError ? err.message : "Failed to create substation.");
    },
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setError(null);
    createMutation.mutate();
  }

  // Create: always starts as Planned or Active (substation-registry.md §10).
  const initialStatusOptions = referenceData.operationalStatuses.filter((status) =>
    ["PLANNED", "ACTIVE"].includes(status.code),
  );

  return (
    <section>
      <h2>Create substation</h2>
      <form onSubmit={handleSubmit}>
        <div>
          <label htmlFor="mnemonic">Mnemonic</label>
          <br />
          <input
            id="mnemonic"
            value={mnemonic}
            onChange={(e) => setMnemonic(e.target.value)}
            required
            maxLength={10}
          />
        </div>
        <div>
          <label htmlFor="official-name">Official name</label>
          <br />
          <input
            id="official-name"
            value={officialName}
            onChange={(e) => setOfficialName(e.target.value)}
            required
            maxLength={150}
          />
        </div>
        <div>
          <label htmlFor="region">Region</label>
          <br />
          <select
            id="region"
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
          <label htmlFor="state">State</label>
          <br />
          <select id="state" value={stateId} onChange={(e) => setStateId(e.target.value)} required>
            <option value="">Select...</option>
            {referenceData.states.map((state) => (
              <option key={state.state_id} value={state.state_id}>
                {state.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="grid-owner">Grid owner</label>
          <br />
          <select
            id="grid-owner"
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
        {error && <p role="alert">{error}</p>}
        <button type="submit" disabled={createMutation.isPending}>
          Create substation
        </button>
      </form>
    </section>
  );
}
