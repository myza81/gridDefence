import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { networkModelApi } from "../api";

/**
 * Situational-awareness summary of the registered transmission network
 * (docs/engineering/03-system-workflow.md's "Network Overview" concept —
 * an entry point, not an analysis). Reflects only what has been registered
 * so far in the Substation Registry and Equipment Registry; an incomplete
 * or partially-registered network is a normal, expected state, never an
 * error (network-model-module.md §19.5).
 */
export function NetworkOverviewPage() {
  const overviewQuery = useQuery({
    queryKey: ["network-model", "overview"],
    queryFn: () => networkModelApi.getOverview(),
  });

  return (
    <section>
      <h2>Network Overview</h2>
      <p>
        A summary of the transmission network as currently registered. This reflects only
        what has been entered into the Substation Registry and Equipment Registry so far —
        the network is expected to grow incrementally, and an incomplete registry is a
        normal working state, not an error.
      </p>

      {overviewQuery.isLoading && <p>Loading network overview...</p>}
      {overviewQuery.isError && <p role="alert">Failed to load network overview.</p>}

      {overviewQuery.data && (
        <dl
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
            gap: "1rem",
            maxWidth: "48rem",
          }}
        >
          <div>
            <dt>Substations</dt>
            <dd style={{ fontSize: "1.5rem", margin: 0 }}>{overviewQuery.data.substation_count}</dd>
          </div>
          <div>
            <dt>Transmission Lines</dt>
            <dd style={{ fontSize: "1.5rem", margin: 0 }}>{overviewQuery.data.circuit_count}</dd>
          </div>
          <div>
            <dt>Multi-Terminal (Tee-Off) Lines</dt>
            <dd style={{ fontSize: "1.5rem", margin: 0 }}>
              {overviewQuery.data.tee_off_circuit_count}
            </dd>
          </div>
          <div>
            <dt>Transformers</dt>
            <dd style={{ fontSize: "1.5rem", margin: 0 }}>{overviewQuery.data.transformer_count}</dd>
          </div>
        </dl>
      )}

      <nav style={{ marginTop: "2rem", display: "flex", gap: "1rem" }}>
        <Link to="/network-model/substations">Browse Substations</Link>
        <Link to="/network-model/traversal">Network Traversal</Link>
      </nav>
    </section>
  );
}
