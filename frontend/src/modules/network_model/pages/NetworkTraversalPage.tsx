import { useMutation, useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { substationRegistryApi } from "../../substation_registry/api";
import { networkModelApi } from "../api";
import type { TraversalResult } from "../types";

interface TraversedLine {
  circuitId: string;
  name: string;
  substationMnemonics: string[];
}

/**
 * Exposes the backend's generic reachability traversal
 * (network-model-module.md §19.4) as a plain engineering exploration tool:
 * pick a starting substation, optionally limit depth, see what is
 * reachable. This is deliberately not a load-pocket or island-detection
 * feature — it answers only "what is reachable from here," nothing more.
 *
 * "Transmission Lines Traversed" is derived client-side from each
 * reachable substation's own connectivity (already-authoritative backend
 * data), filtered to lines whose every terminal substation is also within
 * the reachable set — the backend's own traversal result does not return
 * an edge list directly. See the Phase 5B implementation report's
 * architectural observations for why this is computed here rather than
 * added as a new backend field in this phase.
 */
export function NetworkTraversalPage() {
  const [startSubstationId, setStartSubstationId] = useState("");
  const [maxDepth, setMaxDepth] = useState("");
  const [result, setResult] = useState<TraversalResult | null>(null);

  const substationsQuery = useQuery({
    queryKey: ["network-model", "traversal", "substation-options"],
    queryFn: () => substationRegistryApi.listSubstations({ page_size: 500 }),
  });

  const traverseMutation = useMutation({
    mutationFn: () =>
      networkModelApi.traverse({
        start_substation_id: startSubstationId,
        max_depth: maxDepth === "" ? null : Number(maxDepth),
      }),
    onSuccess: (data) => setResult(data),
  });

  const reachable = result?.reachable_substations ?? [];
  const connectivityQueries = useQueries({
    queries: reachable.map((reachableSubstation) => ({
      queryKey: ["network-model", "connectivity", reachableSubstation.substation_id],
      queryFn: () => networkModelApi.getSubstationConnectivity(reachableSubstation.substation_id),
    })),
  });
  const connectivityStillLoading = connectivityQueries.some((query) => query.isLoading);

  const reachableIds = new Set(reachable.map((reachableSubstation) => reachableSubstation.substation_id));
  const traversedLinesById = new Map<string, TraversedLine>();
  for (const query of connectivityQueries) {
    if (!query.data) {
      continue;
    }
    for (const line of query.data.connected_lines) {
      const allWithinReach = line.terminals.every((terminal) => reachableIds.has(terminal.substation_id));
      if (allWithinReach && !traversedLinesById.has(line.circuit_id)) {
        traversedLinesById.set(line.circuit_id, {
          circuitId: line.circuit_id,
          name: line.circuit_name,
          substationMnemonics: line.terminals.map((terminal) => terminal.substation_mnemonic),
        });
      }
    }
  }
  const traversedLines = Array.from(traversedLinesById.values());

  return (
    <section>
      <h2>Network Traversal</h2>
      <p>
        Explore which substations are electrically reachable from a starting point. This is
        an engineering exploration tool — it does not identify load pockets, islands, or
        perform any scheme-related calculation.
      </p>

      <form
        onSubmit={(event) => {
          event.preventDefault();
          setResult(null);
          traverseMutation.mutate();
        }}
      >
        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="start-substation">Starting substation</label>
          <br />
          <select
            id="start-substation"
            value={startSubstationId}
            onChange={(event) => setStartSubstationId(event.target.value)}
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
          <label htmlFor="max-depth">Maximum depth (optional)</label>
          <br />
          <input
            id="max-depth"
            type="number"
            min={0}
            value={maxDepth}
            onChange={(event) => setMaxDepth(event.target.value)}
          />
        </div>

        <button type="submit" disabled={!startSubstationId || traverseMutation.isPending}>
          {traverseMutation.isPending ? "Traversing..." : "Traverse"}
        </button>
      </form>

      {traverseMutation.isError && <p role="alert">Failed to run traversal.</p>}

      {result && (
        <>
          <h3>Reachable Substations ({result.reachable_substations.length})</h3>
          <table>
            <thead>
              <tr>
                <th>Substation</th>
                <th>Distance (hops)</th>
              </tr>
            </thead>
            <tbody>
              {result.reachable_substations.map((reachableSubstation) => (
                <tr key={reachableSubstation.substation_id}>
                  <td>
                    <Link to={`/network-model/substations/${reachableSubstation.substation_id}`}>
                      {reachableSubstation.substation_mnemonic}
                    </Link>
                  </td>
                  <td>{reachableSubstation.depth}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Transmission Lines Traversed</h3>
          {connectivityStillLoading && <p>Loading connecting lines...</p>}
          {!connectivityStillLoading && traversedLines.length === 0 && (
            <p>No transmission lines connect substations within this reachable set.</p>
          )}
          {!connectivityStillLoading && traversedLines.length > 0 && (
            <ul>
              {traversedLines.map((line) => (
                <li key={line.circuitId}>
                  {line.name} ({line.substationMnemonics.join(" – ")})
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
