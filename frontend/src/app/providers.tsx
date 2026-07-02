import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useState } from "react";

/**
 * Composition root for cross-cutting frontend concerns.
 *
 * Server state lives in TanStack Query (CLAUDE.md §15); UI state stays in
 * React itself. No business-module providers exist yet in Phase 0 — each
 * module adds its own query/mutation hooks under src/modules/<name>/ once
 * that module's implementation phase begins.
 */
export function AppProviders({ children }: PropsWithChildren) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
