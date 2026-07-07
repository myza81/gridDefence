import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { FormEvent } from "react";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import { useAuth } from "../../iam/AuthContext";
import { psseIntegrationApi } from "../api";
import type { EquipmentTopologyMapEntry } from "../types";

/** EquipmentTopologyMap review — clean-match/unmatched/discrepancy results
 * (ADR-006/ADR-007; §8a). Discrepancies require mandatory human review and
 * are never silently resolved; resolving one only records the engineer's
 * classification decision here — it never writes to Equipment Registry. */
export function PsseEquipmentTopologyMapPage() {
  const { topologyVersionId } = useParams<{ topologyVersionId: string }>();
  const { permissions } = useAuth();
  const canReview = permissions.has("psse_integration.import");
  const queryClient = useQueryClient();

  const [matchOutcomeFilter, setMatchOutcomeFilter] = useState("");

  const mapQuery = useQuery({
    queryKey: ["psse-integration", "equipment-map", topologyVersionId, matchOutcomeFilter],
    queryFn: () =>
      psseIntegrationApi.listEquipmentMap(
        topologyVersionId as string,
        matchOutcomeFilter || undefined,
      ),
    enabled: topologyVersionId !== undefined,
  });

  if (mapQuery.isLoading) {
    return <p>Loading equipment correlation...</p>;
  }
  if (mapQuery.isError || !mapQuery.data) {
    return <p role="alert">Failed to load equipment correlation.</p>;
  }

  return (
    <section>
      <h2>Equipment Registry correlation</h2>
      <p>
        Every entry correlates one Equipment Registry circuit terminal with a PSS/E topology
        element within this topology version. Discrepancies must be reviewed and classified
        explicitly — they are never silently resolved.
      </p>

      <select
        aria-label="Filter by match outcome"
        value={matchOutcomeFilter}
        onChange={(e) => setMatchOutcomeFilter(e.target.value)}
      >
        <option value="">All outcomes</option>
        <option value="clean_match">Clean match</option>
        <option value="unmatched">Unmatched</option>
        <option value="discrepancy">Discrepancy</option>
      </select>

      <table style={{ marginTop: "1rem" }}>
        <thead>
          <tr>
            <th>Circuit</th>
            <th>Substation</th>
            <th>Match outcome</th>
            <th>Resolution</th>
            {canReview && <th></th>}
          </tr>
        </thead>
        <tbody>
          {mapQuery.data.items.map((entry) => (
            <EquipmentMapRow
              key={entry.map_id}
              entry={entry}
              canReview={canReview}
              onResolved={() => {
                void queryClient.invalidateQueries({
                  queryKey: ["psse-integration", "equipment-map", topologyVersionId],
                });
              }}
            />
          ))}
          {mapQuery.data.items.length === 0 && (
            <tr>
              <td colSpan={canReview ? 5 : 4}>No entries match this filter.</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

interface EquipmentMapRowProps {
  entry: EquipmentTopologyMapEntry;
  canReview: boolean;
  onResolved: () => void;
}

function EquipmentMapRow({ entry, canReview, onResolved }: EquipmentMapRowProps) {
  const [changeReason, setChangeReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const resolveMutation = useMutation({
    mutationFn: (resolution: "accepted" | "rejected") =>
      psseIntegrationApi.resolveDiscrepancy(entry.map_id, { resolution, change_reason: changeReason }),
    onSuccess: () => {
      setError(null);
      onResolved();
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? err.message : "Failed to resolve discrepancy."),
  });

  function handleSubmit(event: FormEvent<HTMLFormElement>, resolution: "accepted" | "rejected") {
    event.preventDefault();
    resolveMutation.mutate(resolution);
  }

  return (
    <tr>
      <td>
        {entry.circuit_bay_number} ({entry.circuit_id})
      </td>
      <td>{entry.substation_mnemonic}</td>
      <td>{entry.match_outcome}</td>
      <td>
        {entry.discrepancy_resolution
          ? `${entry.discrepancy_resolution} by ${entry.resolved_by?.username ?? "unknown"}`
          : "—"}
      </td>
      {canReview && (
        <td>
          {entry.match_outcome === "discrepancy" && !entry.discrepancy_resolution && (
            <form onSubmit={(e) => handleSubmit(e, "accepted")}>
              <input
                aria-label={`Change reason for ${entry.circuit_bay_number}`}
                value={changeReason}
                onChange={(e) => setChangeReason(e.target.value)}
                placeholder="Change reason"
                required
              />
              <button type="submit" disabled={resolveMutation.isPending}>
                Accept
              </button>
              <button
                type="button"
                disabled={resolveMutation.isPending}
                onClick={() => resolveMutation.mutate("rejected")}
              >
                Reject
              </button>
              {error && <p role="alert">{error}</p>}
            </form>
          )}
        </td>
      )}
    </tr>
  );
}
