import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { useReferenceData } from "../../../reference_data/useReferenceData";
import { substationRegistryApi } from "../../substation_registry/api";
import { automaticLoadSheddingFunctionalityApi } from "../api";
import { deriveFunctionLabel, formatTerminalIdentity } from "../displayHelpers";
import type { SchemeType, TargetType } from "../types";

/** Candidate/capability view (module document §12, §13, §17) — prepared
 * for future UFLS/UVLS integration. Shows every non-decommissioned Bay
 * Terminal functionally ready for the selected scheme type — Available or
 * Assigned alike. This page does not, and cannot yet, show scheme
 * *assignment* status — UFLS/UVLS do not exist yet (module document §4,
 * §9 rule 7, §13's `list_assigned_and_available` composition point).
 * EMLS is never an option here — it has no automatic-functionality
 * prerequisite. */
export function FunctionalityCandidatePage() {
  const referenceData = useReferenceData();

  const [schemeType, setSchemeType] = useState<SchemeType>("UFLS");
  const [substationId, setSubstationId] = useState("");
  const [targetType, setTargetType] = useState<TargetType | "">("");
  const [voltageLevelId, setVoltageLevelId] = useState("");

  const substationsQuery = useQuery({
    queryKey: ["automatic-load-shedding-functionality", "candidates", "substation-options"],
    queryFn: () => substationRegistryApi.listSubstations({ page_size: 500 }),
  });

  const candidatesQuery = useQuery({
    queryKey: [
      "automatic-load-shedding-functionality",
      "candidates",
      { schemeType, substationId, targetType, voltageLevelId },
    ],
    queryFn: () =>
      automaticLoadSheddingFunctionalityApi.listCandidates({
        scheme_type: schemeType,
        substation_id: substationId || undefined,
        target_type: targetType || undefined,
        voltage_level_id: voltageLevelId ? Number(voltageLevelId) : undefined,
      }),
  });

  return (
    <section>
      <h2>Candidate Bay Terminals</h2>
      <p>
        Every Bay Terminal with active, functionally-ready automatic shedding capability for the
        selected scheme type. Scheme assignment status is not shown here — UFLS/UVLS do not exist
        yet in GridDefence; once they do, this view is intended to be composed with each scheme's
        own current assignment set (module document §13).
      </p>

      <div style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", flexWrap: "wrap" }}>
        <select
          aria-label="Scheme type"
          value={schemeType}
          onChange={(e) => setSchemeType(e.target.value as SchemeType)}
        >
          <option value="UFLS">UFLS</option>
          <option value="UVLS">UVLS</option>
        </select>
        <select
          aria-label="Filter by substation"
          value={substationId}
          onChange={(e) => setSubstationId(e.target.value)}
        >
          <option value="">All substations</option>
          {substationsQuery.data?.items.map((substation) => (
            <option key={substation.substation_id} value={substation.substation_id}>
              {substation.mnemonic}
            </option>
          ))}
        </select>
        <select
          aria-label="Filter by terminal type"
          value={targetType}
          onChange={(e) => setTargetType(e.target.value as TargetType | "")}
        >
          <option value="">All terminal (bay) types</option>
          <option value="CIRCUIT_TERMINAL">Circuit Terminal</option>
          <option value="TRANSFORMER_TERMINAL">Transformer Terminal</option>
        </select>
        <select
          aria-label="Filter by voltage level"
          value={voltageLevelId}
          onChange={(e) => setVoltageLevelId(e.target.value)}
        >
          <option value="">All voltage levels</option>
          {referenceData.voltageLevels.map((level) => (
            <option key={level.voltage_level_id} value={level.voltage_level_id}>
              {level.label}
            </option>
          ))}
        </select>
      </div>

      {candidatesQuery.isLoading && <p>Loading candidates...</p>}
      {candidatesQuery.isError && <p role="alert">Failed to load candidates.</p>}

      {candidatesQuery.data && (
        <>
          <h3>Candidates ({candidatesQuery.data.total})</h3>
          <table>
            <thead>
              <tr>
                <th>Terminal Identity</th>
                <th>Terminal Type</th>
                <th>Automatic Load Shedding Function</th>
              </tr>
            </thead>
            <tbody>
              {candidatesQuery.data.items.map((candidate) => (
                <tr key={candidate.id}>
                  <td>
                    {formatTerminalIdentity(
                      candidate.substation_mnemonic,
                      candidate.voltage_level_label,
                      candidate.bay_label,
                    )}
                  </td>
                  <td>
                    {candidate.target_type === "CIRCUIT_TERMINAL"
                      ? "Circuit Terminal"
                      : "Transformer Terminal"}
                  </td>
                  <td>{deriveFunctionLabel(candidate.ufls_function, candidate.uvls_function)}</td>
                </tr>
              ))}
              {candidatesQuery.data.items.length === 0 && (
                <tr>
                  <td colSpan={3}>No candidate bay terminals match your filters.</td>
                </tr>
              )}
            </tbody>
          </table>
        </>
      )}
    </section>
  );
}
