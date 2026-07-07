import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { psseIntegrationApi } from "../api";

/** The currently-active TopologyVersion and LoadSnapshot — what the rest of
 * GridDefence (e.g. a future Network Model) would resolve against right
 * now. Never more than one Current record per type (ADR-003; F5). */
export function PsseCurrentStatusPage() {
  const statusQuery = useQuery({
    queryKey: ["psse-integration", "current-status"],
    queryFn: () => psseIntegrationApi.getCurrentStatus(),
  });

  if (statusQuery.isLoading) {
    return <p>Loading current status...</p>;
  }
  if (statusQuery.isError || !statusQuery.data) {
    return <p role="alert">Failed to load current status.</p>;
  }

  const { current_topology_version: topology, current_load_snapshot: snapshot } =
    statusQuery.data;

  return (
    <section>
      <h2>Current PSS/E status</h2>

      <h3>Current topology</h3>
      {topology ? (
        <dl>
          <dt>Signature</dt>
          <dd>{topology.signature}</dd>
          <dt>Buses / Branches / Transformers</dt>
          <dd>
            {topology.bus_count} / {topology.branch_count} / {topology.transformer_count}
          </dd>
          <dt>Promoted at</dt>
          <dd>{topology.promoted_at ?? "—"}</dd>
        </dl>
      ) : (
        <p>No TopologyVersion has been activated yet.</p>
      )}
      {topology && (
        <p>
          <Link
            to={`/psse-integration/topology-versions/${topology.topology_version_id}/equipment-map`}
          >
            Review Equipment Registry correlation
          </Link>
        </p>
      )}

      <h3>Current load snapshot</h3>
      {snapshot ? (
        <dl>
          <dt>Loads / Generators</dt>
          <dd>
            {snapshot.load_count} / {snapshot.generator_count}
          </dd>
          <dt>Promoted at</dt>
          <dd>{snapshot.promoted_at ?? "—"}</dd>
        </dl>
      ) : (
        <p>No LoadSnapshot has been activated yet.</p>
      )}
    </section>
  );
}
