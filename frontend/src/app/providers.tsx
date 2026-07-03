import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { PropsWithChildren } from "react";
import { useState } from "react";

import { AuthProvider } from "../modules/iam/AuthContext";

/**
 * Composition root for cross-cutting frontend concerns.
 *
 * Server state lives in TanStack Query (CLAUDE.md §15); UI state stays in
 * React itself. IAM's AuthProvider is composed here (not inside
 * modules/iam's own routes) because authentication is cross-cutting — every
 * other module's routes depend on knowing the current session.
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

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
