import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { StatusPage } from "../components/layout/StatusPage";

/**
 * Root route table. Each business module registers its own routes here once
 * it exists (docs/architecture/implementation-plan.md §3) — Phase 0 defines
 * only the landing/status route.
 */
const router = createBrowserRouter([
  {
    path: "/",
    element: (
      <AppShell>
        <StatusPage />
      </AppShell>
    ),
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
