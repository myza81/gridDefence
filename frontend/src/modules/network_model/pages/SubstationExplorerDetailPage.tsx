import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { networkModelApi } from "../api";
import type { NeighbourSubstation } from "../types";

/** One neighbour row per distinct substation, even if several parallel
 * transmission lines connect to it — this page shows the substation-level
 * relationship; per-line detail belongs to the Connectivity View. */
function dedupeNeighbours(neighbours: NeighbourSubstation[]): NeighbourSubstation[] {
  const seen = new Map<string, NeighbourSubstation>();
  for (const neighbour of neighbours) {
    if (!seen.has(neighbour.substation_id)) {
      seen.set(neighbour.substation_id, neighbour);
    }
  }
  return Array.from(seen.values());
}

/**
 * A substation's engineering summary: general information, its Bays, its
 * neighbouring substations, and its connected transmission lines — grouped
 * by engineering relationship (network-model-module.md §19.3), not by
 * database table. Every section degrades gracefully when nothing has been
 * registered yet (§19.5) — an isolated or partially-registered substation
 * is a normal, fully navigable state, never an error.
 */
export function SubstationExplorerDetailPage() {
  const { substationId } = useParams<{ substationId: string }>();

  const connectivityQuery = useQuery({
    queryKey: ["network-model", "connectivity", substationId],
    queryFn: () => networkModelApi.getSubstationConnectivity(substationId as string),
    enabled: substationId !== undefined,
  });

  const equipmentQuery = useQuery({
    queryKey: ["network-model", "equipment", substationId],
    queryFn: () => networkModelApi.getSubstationEquipment(substationId as string),
    enabled: substationId !== undefined,
  });

  if (connectivityQuery.isLoading || equipmentQuery.isLoading) {
    return <p>Loading substation...</p>;
  }
  if (
    connectivityQuery.isError ||
    equipmentQuery.isError ||
    !connectivityQuery.data ||
    !equipmentQuery.data
  ) {
    return <p role="alert">Substation not found.</p>;
  }

  const connectivity = connectivityQuery.data;
  const equipment = equipmentQuery.data;
  const neighbours = dedupeNeighbours(connectivity.neighbours);

  return (
    <section>
      <h2>
        {connectivity.substation_mnemonic} — {connectivity.substation_official_name}
      </h2>

      <nav style={{ display: "flex", gap: "1rem", margin: "1rem 0" }}>
        <Link to={`/network-model/substations/${substationId}/bays`}>View Bays</Link>
        <Link to={`/network-model/substations/${substationId}/connectivity`}>View Connectivity</Link>
      </nav>

      <details open style={{ marginBottom: "1rem" }}>
        <summary>Transformer Bays ({equipment.transformer_bays.length})</summary>
        {equipment.transformer_bays.length === 0 ? (
          <p>No Transformer Bays registered at this substation yet.</p>
        ) : (
          <ul>
            {equipment.transformer_bays.map((bay) => (
              <li key={bay.transformer_id}>
                {bay.generated_short_name} — hosts a {bay.hv_voltage_level_label}/
                {bay.lv_voltage_level_label} transformer
                {bay.capacity_mva !== null ? ` (${bay.capacity_mva} MVA)` : ""}
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open style={{ marginBottom: "1rem" }}>
        <summary>Line Bays ({equipment.line_bays.length})</summary>
        {equipment.line_bays.length === 0 ? (
          <p>No Line Bays registered at this substation yet.</p>
        ) : (
          <ul>
            {equipment.line_bays.map((bay) => (
              <li key={bay.circuit_terminal_id}>
                Bay {bay.circuit_bay_number} — hosts transmission line {bay.circuit_name} (breaker{" "}
                {bay.breaker_number})
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open style={{ marginBottom: "1rem" }}>
        <summary>Connected Substations ({neighbours.length})</summary>
        {neighbours.length === 0 ? (
          <p>No neighbouring substations registered yet.</p>
        ) : (
          <ul>
            {neighbours.map((neighbour) => (
              <li key={neighbour.substation_id}>
                <Link to={`/network-model/substations/${neighbour.substation_id}`}>
                  {neighbour.substation_mnemonic} — {neighbour.substation_official_name}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </details>

      <details open>
        <summary>Connected Transmission Lines ({connectivity.connected_lines.length})</summary>
        {connectivity.connected_lines.length === 0 ? (
          <p>No transmission lines registered at this substation yet.</p>
        ) : (
          <ul>
            {connectivity.connected_lines.map((line) => (
              <li key={line.circuit_id}>
                {line.circuit_name} (Bay {line.bay_number}, {line.voltage_level_label})
                {line.is_tee_off ? " — multi-terminal line" : ""}
              </li>
            ))}
          </ul>
        )}
      </details>
    </section>
  );
}
