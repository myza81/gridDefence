import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { equipmentRegistryApi } from "../../equipment_registry/api";
import { substationRegistryApi } from "../../substation_registry/api";
import { networkModelApi } from "../api";
import type { TraversalVerificationResult } from "../types";

/**
 * Phase 7F — Operational Snapshot Verification Workspace
 * (docs/architecture/network-model-module.md §19.10). An engineering
 * diagnostic page, independent of the Network Traversal page (unchanged) —
 * it exists to let an engineer verify that the Operational Snapshot
 * faithfully represents the imported PSS/E network before that snapshot
 * becomes the foundation of UFLS/UVLS/EMLS/Heatmap/Analytics. Bus-level
 * BFS remains the authoritative computation; this page only presents that
 * one computation's result at Bus, Switchyard, and Substation granularity
 * (Operational Projections, operational-correlation-architecture.md §4.2)
 * — clarity over appearance, tables over graphics, per this phase's own
 * UI instruction.
 */
export function OperationalSnapshotVerificationPage() {
  const [startSubstationId, setStartSubstationId] = useState("");
  const [startVoltageYardId, setStartVoltageYardId] = useState("");
  const [maxDepth, setMaxDepth] = useState("");
  const [projection, setProjection] = useState<"bus" | "switchyard" | "substation">("substation");
  const [result, setResult] = useState<TraversalVerificationResult | null>(null);

  const snapshotSummaryQuery = useQuery({
    queryKey: ["network-model", "verification", "snapshot-summary"],
    queryFn: () => networkModelApi.getSnapshotSummary(),
  });

  const substationsQuery = useQuery({
    queryKey: ["network-model", "verification", "substation-options"],
    queryFn: () => substationRegistryApi.listSubstations({ page_size: 500 }),
  });

  const voltageYardsQuery = useQuery({
    queryKey: ["network-model", "verification", "voltage-yards", startSubstationId],
    queryFn: () => equipmentRegistryApi.listVoltageYards({ substation_id: startSubstationId }),
    enabled: startSubstationId !== "",
  });

  const verifyMutation = useMutation({
    mutationFn: () =>
      networkModelApi.verifyPath({
        start_substation_id: startSubstationId,
        start_voltage_yard_id: startVoltageYardId === "" ? null : startVoltageYardId,
        max_depth: maxDepth === "" ? null : Number(maxDepth),
      }),
    onSuccess: (data) => setResult(data),
  });

  return (
    <section>
      <h2>Operational Snapshot Verification Workspace</h2>
      <p>
        An engineering diagnostic tool — verify that the Operational Snapshot faithfully
        represents the imported PSS/E network. This is independent from the Network Traversal
        page and does not replace it.
      </p>

      <h3>Section 1 — Snapshot Summary</h3>
      {snapshotSummaryQuery.isLoading && <p>Loading snapshot summary...</p>}
      {snapshotSummaryQuery.data && (
        <table>
          <tbody>
            <tr>
              <th style={{ textAlign: "left" }}>Active Topology Version</th>
              <td>
                {snapshotSummaryQuery.data.topology_version_id ?? "None"}{" "}
                {snapshotSummaryQuery.data.topology_version_status &&
                  `(${snapshotSummaryQuery.data.topology_version_status})`}
              </td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Active Load Snapshot</th>
              <td>
                {snapshotSummaryQuery.data.load_snapshot_id ?? "None"}{" "}
                {snapshotSummaryQuery.data.load_snapshot_status &&
                  `(${snapshotSummaryQuery.data.load_snapshot_status})`}
              </td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Import Date</th>
              <td>{snapshotSummaryQuery.data.import_date ?? "—"}</td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Bus Count</th>
              <td>{snapshotSummaryQuery.data.bus_count}</td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Branch Count</th>
              <td>{snapshotSummaryQuery.data.branch_count}</td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Transformer Count</th>
              <td>{snapshotSummaryQuery.data.transformer_count}</td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Load Count</th>
              <td>{snapshotSummaryQuery.data.load_count}</td>
            </tr>
            <tr>
              <th style={{ textAlign: "left" }}>Generator Count</th>
              <td>{snapshotSummaryQuery.data.generator_count}</td>
            </tr>
          </tbody>
        </table>
      )}

      <h3>Section 2 — Electrical Path Verification</h3>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          setResult(null);
          verifyMutation.mutate();
        }}
      >
        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="verify-start-substation">Starting Substation</label>
          <br />
          <select
            id="verify-start-substation"
            value={startSubstationId}
            onChange={(event) => {
              setStartSubstationId(event.target.value);
              setStartVoltageYardId("");
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
          <label htmlFor="verify-start-switchyard">Starting Switchyard (optional)</label>
          <br />
          <select
            id="verify-start-switchyard"
            value={startVoltageYardId}
            onChange={(event) => setStartVoltageYardId(event.target.value)}
            disabled={startSubstationId === ""}
          >
            <option value="">Whole substation (every correlated Bus)</option>
            {voltageYardsQuery.data?.map((yard) => (
              <option key={yard.voltage_yard_id} value={yard.voltage_yard_id}>
                {yard.voltage_level_label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: "0.75rem" }}>
          <label htmlFor="verify-max-depth">Maximum depth (optional)</label>
          <br />
          <input
            id="verify-max-depth"
            type="number"
            min={0}
            value={maxDepth}
            onChange={(event) => setMaxDepth(event.target.value)}
          />
        </div>

        <button type="submit" disabled={!startSubstationId || verifyMutation.isPending}>
          {verifyMutation.isPending ? "Running traversal..." : "Run Traversal"}
        </button>
      </form>

      {verifyMutation.isError && <p role="alert">Failed to run path verification.</p>}

      {result && (
        <>
          <h4>Electrical Path</h4>
          {result.path_steps.length === 0 && (
            <p>No path steps — the starting point has no Operational Bus to traverse from.</p>
          )}
          {result.path_steps.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>Depth</th>
                  <th>From Bus</th>
                  <th>Crossing</th>
                  <th>Circuit ID</th>
                  <th>To Bus</th>
                </tr>
              </thead>
              <tbody>
                {result.path_steps.map((step, index) => (
                  <tr key={index}>
                    <td>{step.depth}</td>
                    <td>
                      {step.from_bus_name ?? step.from_bus_number} ({step.from_bus_number})
                    </td>
                    <td>{step.edge_type === "TRANSFORMER" ? "Transformer" : "Circuit"}</td>
                    <td>{step.ckt_id}</td>
                    <td>
                      {step.to_bus_name ?? step.to_bus_number} ({step.to_bus_number})
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3>Section 3 — Operational Bus View</h3>
          <table>
            <thead>
              <tr>
                <th>Bus Number</th>
                <th>Bus Name</th>
                <th>Base kV</th>
                <th>Classification</th>
                <th>In Service</th>
                <th>Depth</th>
                <th>Registered Substation</th>
                <th>Registered Switchyard</th>
                <th>Correlation Status</th>
              </tr>
            </thead>
            <tbody>
              {result.buses.map((pathBus) => (
                <tr key={pathBus.bus.bus_number}>
                  <td>{pathBus.bus.bus_number}</td>
                  <td>{pathBus.bus.bus_name ?? "—"}</td>
                  <td>{pathBus.base_kv}</td>
                  <td>{pathBus.bus.bus_classification}</td>
                  <td>{pathBus.bus.in_service === null ? "Unknown" : pathBus.bus.in_service ? "Yes" : "No"}</td>
                  <td>{pathBus.depth}</td>
                  <td>{pathBus.bus.substation_mnemonic ?? "—"}</td>
                  <td>{pathBus.bus.voltage_yard_id ?? "—"}</td>
                  <td>{pathBus.bus.correlation_status}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <h3>Section 4 — Traversed Branches</h3>
          <table>
            <thead>
              <tr>
                <th>From Bus</th>
                <th>To Bus</th>
                <th>Circuit ID</th>
                <th>In Service</th>
                <th>Circuit</th>
                <th>Bay Number</th>
                <th>Correlation Status</th>
              </tr>
            </thead>
            <tbody>
              {result.branches.map((branch) => (
                <tr key={branch.topology_branch_id}>
                  <td>{branch.from_bus_number}</td>
                  <td>{branch.to_bus_number}</td>
                  <td>{branch.ckt_id}</td>
                  <td>{branch.in_service === null ? "Unknown" : branch.in_service ? "Yes" : "No"}</td>
                  <td>{branch.circuit_id ?? "—"}</td>
                  <td>{branch.circuit_bay_number ?? "—"}</td>
                  <td>{branch.correlation_status}</td>
                </tr>
              ))}
              {result.branches.length === 0 && (
                <tr>
                  <td colSpan={7}>No branches within the reached component.</td>
                </tr>
              )}
            </tbody>
          </table>

          <h3>Section 5 — Traversed Transformers</h3>
          <table>
            <thead>
              <tr>
                <th>HV Bus</th>
                <th>LV Bus</th>
                <th>Circuit ID</th>
                <th>In Service</th>
                <th>Registered Circuit</th>
                <th>Correlation Status</th>
              </tr>
            </thead>
            <tbody>
              {result.transformers.map((transformer) => (
                <tr key={transformer.topology_transformer_id}>
                  <td>{transformer.from_bus_number}</td>
                  <td>{transformer.to_bus_number}</td>
                  <td>{transformer.ckt_id}</td>
                  <td>
                    {transformer.in_service === null ? "Unknown" : transformer.in_service ? "Yes" : "No"}
                  </td>
                  <td>{transformer.circuit_id ?? "—"}</td>
                  <td>{transformer.correlation_status}</td>
                </tr>
              ))}
              {result.transformers.length === 0 && (
                <tr>
                  <td colSpan={6}>No transformers within the reached component.</td>
                </tr>
              )}
            </tbody>
          </table>

          <h3>Section 6 — Traversal Statistics</h3>
          <table>
            <tbody>
              <tr>
                <th style={{ textAlign: "left" }}>Operational Buses Traversed</th>
                <td>{result.statistics.operational_buses_traversed}</td>
              </tr>
              <tr>
                <th style={{ textAlign: "left" }}>Operational Branches Traversed</th>
                <td>{result.statistics.operational_branches_traversed}</td>
              </tr>
              <tr>
                <th style={{ textAlign: "left" }}>Operational Transformers Traversed</th>
                <td>{result.statistics.operational_transformers_traversed}</td>
              </tr>
              <tr>
                <th style={{ textAlign: "left" }}>Operational Switchyards Traversed</th>
                <td>{result.statistics.operational_switchyards_traversed}</td>
              </tr>
              <tr>
                <th style={{ textAlign: "left" }}>Registered Substations Correlated</th>
                <td>{result.statistics.registered_substations_correlated}</td>
              </tr>
              <tr>
                <th style={{ textAlign: "left" }}>Registered Switchyards Correlated</th>
                <td>{result.statistics.registered_switchyards_correlated}</td>
              </tr>
            </tbody>
          </table>

          <h3>Section 7 — Correlation Summary</h3>
          <table>
            <thead>
              <tr>
                <th>Object Type</th>
                <th>Total</th>
                <th>Correlated</th>
                <th>Unmatched</th>
                <th>Outside Scope</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Bus</td>
                <td>{result.correlation_summary.bus.total}</td>
                <td>{result.correlation_summary.bus.correlated}</td>
                <td>{result.correlation_summary.bus.unmatched}</td>
                <td>{result.correlation_summary.bus.outside_scope}</td>
              </tr>
              <tr>
                <td>Branch</td>
                <td>{result.correlation_summary.branch.total}</td>
                <td>{result.correlation_summary.branch.correlated}</td>
                <td>{result.correlation_summary.branch.unmatched}</td>
                <td>{result.correlation_summary.branch.outside_scope}</td>
              </tr>
              <tr>
                <td>Transformer</td>
                <td>{result.correlation_summary.transformer.total}</td>
                <td>{result.correlation_summary.transformer.correlated}</td>
                <td>{result.correlation_summary.transformer.unmatched}</td>
                <td>{result.correlation_summary.transformer.outside_scope}</td>
              </tr>
            </tbody>
          </table>

          <h3>Section 8 — Projection Comparison</h3>
          <p>
            All three projections originate from the one traversal above — no recalculation, no
            separate graph.
          </p>
          <div style={{ marginBottom: "0.75rem" }}>
            <label>
              <input
                type="radio"
                name="projection"
                value="bus"
                checked={projection === "bus"}
                onChange={() => setProjection("bus")}
              />{" "}
              Operational Bus Projection
            </label>{" "}
            <label>
              <input
                type="radio"
                name="projection"
                value="switchyard"
                checked={projection === "switchyard"}
                onChange={() => setProjection("switchyard")}
              />{" "}
              Operational Switchyard Projection
            </label>{" "}
            <label>
              <input
                type="radio"
                name="projection"
                value="substation"
                checked={projection === "substation"}
                onChange={() => setProjection("substation")}
              />{" "}
              Registered Substation Projection
            </label>
          </div>

          {projection === "bus" && (
            <table>
              <thead>
                <tr>
                  <th>Bus Number</th>
                  <th>Bus Name</th>
                  <th>Depth</th>
                </tr>
              </thead>
              <tbody>
                {result.projections.bus_projection.map((entry) => (
                  <tr key={entry.bus_number}>
                    <td>{entry.bus_number}</td>
                    <td>{entry.bus_name ?? "—"}</td>
                    <td>{entry.depth}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {projection === "switchyard" && (
            <table>
              <thead>
                <tr>
                  <th>Substation</th>
                  <th>Base kV</th>
                  <th>Registered Switchyard</th>
                  <th>Depth</th>
                  <th>Bus Count</th>
                </tr>
              </thead>
              <tbody>
                {result.projections.switchyard_projection.map((entry, index) => (
                  <tr key={index}>
                    <td>{entry.substation_mnemonic}</td>
                    <td>{entry.base_kv}</td>
                    <td>{entry.voltage_yard_id ?? "Not registered"}</td>
                    <td>{entry.depth}</td>
                    <td>{entry.bus_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {projection === "substation" && (
            <table>
              <thead>
                <tr>
                  <th>Substation</th>
                  <th>Depth</th>
                </tr>
              </thead>
              <tbody>
                {result.projections.substation_projection.map((entry) => (
                  <tr key={entry.substation_id}>
                    <td>{entry.substation_mnemonic}</td>
                    <td>{entry.depth}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </section>
  );
}
