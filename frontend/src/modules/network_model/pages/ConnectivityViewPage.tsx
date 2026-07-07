import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { networkModelApi } from "../api";

/**
 * Substation -> Neighbouring Substations -> Connecting Transmission Lines,
 * with simple hop-by-hop navigation to a neighbour's own Connectivity View
 * (docs/engineering/03-system-workflow.md's "Electrical Neighbours"
 * question). No graphical topology is rendered — a grouped, navigable list
 * is preferred (engineering usability over visual sophistication).
 */

interface NeighbourGroup {
  substationId: string;
  mnemonic: string;
  officialName: string;
  lineNames: string[];
}

export function ConnectivityViewPage() {
  const { substationId } = useParams<{ substationId: string }>();

  const connectivityQuery = useQuery({
    queryKey: ["network-model", "connectivity", substationId],
    queryFn: () => networkModelApi.getSubstationConnectivity(substationId as string),
    enabled: substationId !== undefined,
  });

  if (connectivityQuery.isLoading) {
    return <p>Loading connectivity...</p>;
  }
  if (connectivityQuery.isError || !connectivityQuery.data) {
    return <p role="alert">Substation not found.</p>;
  }

  const connectivity = connectivityQuery.data;

  const groupsById = new Map<string, NeighbourGroup>();
  for (const neighbour of connectivity.neighbours) {
    const existing = groupsById.get(neighbour.substation_id);
    if (existing) {
      existing.lineNames.push(neighbour.via_circuit_name);
    } else {
      groupsById.set(neighbour.substation_id, {
        substationId: neighbour.substation_id,
        mnemonic: neighbour.substation_mnemonic,
        officialName: neighbour.substation_official_name,
        lineNames: [neighbour.via_circuit_name],
      });
    }
  }
  const groups = Array.from(groupsById.values());

  return (
    <section>
      <h2>
        Connectivity — {connectivity.substation_mnemonic} ({connectivity.substation_official_name})
      </h2>

      {groups.length === 0 ? (
        <p>No neighbouring substations registered yet.</p>
      ) : (
        <ul>
          {groups.map((group) => (
            <li key={group.substationId} style={{ marginBottom: "1rem" }}>
              <Link to={`/network-model/substations/${group.substationId}/connectivity`}>
                {group.mnemonic} — {group.officialName}
              </Link>
              <ul>
                {group.lineNames.map((lineName, index) => (
                  <li key={`${group.substationId}-${index}`}>via {lineName}</li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}

      <nav style={{ marginTop: "1rem" }}>
        <Link to={`/network-model/substations/${substationId}`}>Back to Substation</Link>
      </nav>
    </section>
  );
}
