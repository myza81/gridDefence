import { useQuery } from "@tanstack/react-query";

import { psseIntegrationApi } from "./api";
import type { JobStatus } from "./types";

const POLL_INTERVAL_MS = 1000;

/**
 * Polls an RQ job's status (preview/commit run asynchronously —
 * implementation-plan.md §4) until it reaches a terminal state
 * (`finished`/`failed`). With `RQ_ASYNC=false` in tests the job is already
 * terminal on the very first fetch, so this resolves immediately there too.
 */
export function useJobPolling(jobId: string | null) {
  return useQuery<JobStatus>({
    queryKey: ["psse-integration", "job", jobId],
    queryFn: () => psseIntegrationApi.getJobStatus(jobId as string),
    enabled: jobId !== null,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "finished" || status === "failed" ? false : POLL_INTERVAL_MS;
    },
  });
}
