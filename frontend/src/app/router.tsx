import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { StatusPage } from "../components/layout/StatusPage";
import { LoginPage } from "../modules/iam/pages/LoginPage";
import { PermissionsPage } from "../modules/iam/pages/PermissionsPage";
import { RolesPage } from "../modules/iam/pages/RolesPage";
import { UsersPage } from "../modules/iam/pages/UsersPage";
import { ProtectedRoute } from "../modules/iam/ProtectedRoute";

/**
 * Root route table. Each business module registers its own routes here once
 * it exists (docs/architecture/implementation-plan.md §3). IAM (Phase 1)
 * adds /login plus its protected management pages; the landing/status route
 * from Phase 0 stays public.
 */
const router = createBrowserRouter([
  {
    path: "/login",
    element: (
      <AppShell>
        <LoginPage />
      </AppShell>
    ),
  },
  {
    path: "/",
    element: (
      <AppShell>
        <StatusPage />
      </AppShell>
    ),
  },
  {
    path: "/users",
    element: (
      <AppShell>
        <ProtectedRoute>
          <UsersPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/roles",
    element: (
      <AppShell>
        <ProtectedRoute>
          <RolesPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/permissions",
    element: (
      <AppShell>
        <ProtectedRoute>
          <PermissionsPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
