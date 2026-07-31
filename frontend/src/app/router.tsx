import { createBrowserRouter, Outlet, RouterProvider } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { LoginPage } from "../modules/iam/pages/LoginPage";
import { ProtectedRoute } from "../modules/iam/ProtectedRoute";
import { authenticatedRoutes } from "./routes";

/**
 * Authenticated layout route (Phase D — Application Shell V2). Gating runs
 * FIRST (ProtectedRoute), so an anonymous visitor is redirected to /login
 * without ever rendering the shell chrome; only then does every child route
 * render inside the permanent Application Shell V2 via <Outlet/>. This is what
 * puts all authenticated pages inside the shared frame while keeping /login a
 * separate full-bleed page.
 */
function ProtectedShell() {
  return (
    <ProtectedRoute>
      <AppShell>
        <Outlet />
      </AppShell>
    </ProtectedRoute>
  );
}

const router = createBrowserRouter([
  {
    // The approved login mockup is a full-bleed page with its own branding —
    // it is deliberately rendered OUTSIDE the shell (no app header/nav chrome).
    path: "/login",
    element: <LoginPage />,
  },
  {
    element: <ProtectedShell />,
    children: authenticatedRoutes,
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
