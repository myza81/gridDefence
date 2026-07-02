import { useQuery } from "@tanstack/react-query";

import { getHealth } from "../../api/client";
import { StatusBadge } from "../ui/StatusBadge";

/**
 * Phase 0 landing page: proves the frontend can reach the backend through
 * TanStack Query + the shared API client. No business-module content lives
 * here — each module's own routes are added under src/modules/<name>/
 * starting with its own implementation phase.
 */
export function StatusPage() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
  });

  return (
    <section>
      <h1>GridDefence</h1>
      <p>Engineering platform for transmission grid defence schemes.</p>

      <h2>Backend status</h2>
      {isLoading && <StatusBadge label="checking..." tone="pending" />}
      {isError && <StatusBadge label="unreachable" tone="error" />}
      {data && <StatusBadge label={`${data.status} (${data.environment})`} tone="ok" />}
    </section>
  );
}
