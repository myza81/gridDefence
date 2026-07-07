import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { networkModelApi } from "../api";
import type { SubstationConnectivity } from "../types";

interface UnifiedBayRow {
  key: string;
  bayName: string;
  bayType: "Transformer Bay" | "Line Bay";
  hostedPrimaryEquipment: string;
  breakerNumber: string;
  connectedLine: string;
  neighbouringSubstation: string;
  operationalStatusCode: string;
}

/** A Line Bay's neighbouring substation(s) are read from this substation's
 * own connectivity data (never assuming exactly one — a tee-off line bay
 * has more than one neighbour, network-model-module.md §19.3). */
function neighboursForCircuit(connectivity: SubstationConnectivity, circuitId: string): string {
  const line = connectivity.connected_lines.find((candidate) => candidate.circuit_id === circuitId);
  if (!line) {
    return "—";
  }
  const others = line.terminals.filter((terminal) => terminal.substation_id !== connectivity.substation_id);
  return others.length > 0 ? others.map((terminal) => terminal.substation_mnemonic).join(", ") : "—";
}

/**
 * The primary engineering object of the Network Model: every Bay at a
 * substation, Transformer Bay and Line Bay together, presented as one
 * unified engineering list (docs/engineering/02-engineering-concepts.md,
 * "Bay"; EDR-005). A Bay's own identity — its name, its breaker — is
 * independent of the Primary Equipment it currently hosts. Implementation
 * names (`CircuitTerminal`, `TransformerTerminal`) are never shown.
 *
 * A Transformer Bay's own breaker identifier is not currently exposed by
 * the backend at this DTO's granularity (see the Phase 5B implementation
 * report's architectural observations) — shown as "Not available" rather
 * than omitted or guessed.
 */
export function BayViewPage() {
  const { substationId } = useParams<{ substationId: string }>();

  const equipmentQuery = useQuery({
    queryKey: ["network-model", "equipment", substationId],
    queryFn: () => networkModelApi.getSubstationEquipment(substationId as string),
    enabled: substationId !== undefined,
  });

  const connectivityQuery = useQuery({
    queryKey: ["network-model", "connectivity", substationId],
    queryFn: () => networkModelApi.getSubstationConnectivity(substationId as string),
    enabled: substationId !== undefined,
  });

  if (equipmentQuery.isLoading || connectivityQuery.isLoading) {
    return <p>Loading Bays...</p>;
  }
  if (
    equipmentQuery.isError ||
    connectivityQuery.isError ||
    !equipmentQuery.data ||
    !connectivityQuery.data
  ) {
    return <p role="alert">Substation not found.</p>;
  }

  const equipment = equipmentQuery.data;
  const connectivity = connectivityQuery.data;

  const bays: UnifiedBayRow[] = [
    ...equipment.transformer_bays.map(
      (bay): UnifiedBayRow => ({
        key: `transformer-${bay.transformer_id}`,
        bayName: bay.generated_short_name,
        bayType: "Transformer Bay",
        hostedPrimaryEquipment: `${bay.hv_voltage_level_label}/${bay.lv_voltage_level_label} Transformer${
          bay.capacity_mva !== null ? ` (${bay.capacity_mva} MVA)` : ""
        }`,
        breakerNumber: "Not available",
        connectedLine: "—",
        neighbouringSubstation: "—",
        operationalStatusCode: bay.operational_status_code,
      }),
    ),
    ...equipment.line_bays.map(
      (bay): UnifiedBayRow => ({
        key: `line-${bay.circuit_terminal_id}`,
        bayName: `Bay ${bay.circuit_bay_number}`,
        bayType: "Line Bay",
        hostedPrimaryEquipment: `Transmission Line ${bay.circuit_name}`,
        breakerNumber: bay.breaker_number,
        connectedLine: bay.circuit_name,
        neighbouringSubstation: neighboursForCircuit(connectivity, bay.circuit_id),
        operationalStatusCode: bay.operational_status_code,
      }),
    ),
  ];

  return (
    <section>
      <h2>
        Bays at {connectivity.substation_mnemonic} — {connectivity.substation_official_name}
      </h2>
      <p>
        A Bay is a permanent engineering identity at this substation. The Primary Equipment
        a Bay hosts — a transformer or a transmission line — may be replaced over time
        without the Bay itself changing.
      </p>

      {bays.length === 0 ? (
        <p>No Bays registered at this substation yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Bay Name</th>
              <th>Bay Type</th>
              <th>Hosted Primary Equipment</th>
              <th>Breaker</th>
              <th>Connected Transmission Line</th>
              <th>Neighbouring Substation</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {bays.map((bay) => (
              <tr key={bay.key}>
                <td>{bay.bayName}</td>
                <td>{bay.bayType}</td>
                <td>{bay.hostedPrimaryEquipment}</td>
                <td>{bay.breakerNumber}</td>
                <td>{bay.connectedLine}</td>
                <td>{bay.neighbouringSubstation}</td>
                <td>{bay.operationalStatusCode}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <nav style={{ marginTop: "1rem" }}>
        <Link to={`/network-model/substations/${substationId}`}>Back to Substation</Link>
      </nav>
    </section>
  );
}
