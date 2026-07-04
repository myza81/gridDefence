import { createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { StatusPage } from "../components/layout/StatusPage";
import { CircuitCreatePage } from "../modules/equipment_registry/pages/CircuitCreatePage";
import { CircuitDetailPage } from "../modules/equipment_registry/pages/CircuitDetailPage";
import { CircuitListPage } from "../modules/equipment_registry/pages/CircuitListPage";
import { TransformerCreatePage } from "../modules/equipment_registry/pages/TransformerCreatePage";
import { TransformerDetailPage } from "../modules/equipment_registry/pages/TransformerDetailPage";
import { TransformerListPage } from "../modules/equipment_registry/pages/TransformerListPage";
import { LoginPage } from "../modules/iam/pages/LoginPage";
import { PermissionsPage } from "../modules/iam/pages/PermissionsPage";
import { RolesPage } from "../modules/iam/pages/RolesPage";
import { UsersPage } from "../modules/iam/pages/UsersPage";
import { ProtectedRoute } from "../modules/iam/ProtectedRoute";
import { SubstationCreatePage } from "../modules/substation_registry/pages/SubstationCreatePage";
import { SubstationDetailPage } from "../modules/substation_registry/pages/SubstationDetailPage";
import { SubstationListPage } from "../modules/substation_registry/pages/SubstationListPage";

/**
 * Root route table. Each business module registers its own routes here once
 * it exists (docs/architecture/implementation-plan.md §3). IAM (Phase 1)
 * adds /login plus its protected management pages; Substation Registry
 * (Phase 2) adds /substations; Equipment Registry (Phase 3) adds /circuits;
 * Transformer Registry (Phase 3.5) adds /transformers. The landing/status
 * route from Phase 0 stays public.
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
  {
    path: "/substations",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/substations/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/substations/:substationId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <SubstationDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/circuits",
    element: (
      <AppShell>
        <ProtectedRoute>
          <CircuitListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/circuits/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <CircuitCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/circuits/:circuitId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <CircuitDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/transformers",
    element: (
      <AppShell>
        <ProtectedRoute>
          <TransformerListPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/transformers/new",
    element: (
      <AppShell>
        <ProtectedRoute>
          <TransformerCreatePage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
  {
    path: "/transformers/:transformerId",
    element: (
      <AppShell>
        <ProtectedRoute>
          <TransformerDetailPage />
        </ProtectedRoute>
      </AppShell>
    ),
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
