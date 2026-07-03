import type { PropsWithChildren } from "react";
import { Navigate } from "react-router-dom";

import { useAuth } from "./AuthContext";

/** Client-side route gating only — the backend is the authority (CLAUDE.md A12, A10). */
export function ProtectedRoute({ children }: PropsWithChildren) {
  const { token, isLoadingCurrentUser } = useAuth();

  if (token === null) {
    return <Navigate to="/login" replace />;
  }

  if (isLoadingCurrentUser) {
    return <p>Loading session...</p>;
  }

  return <>{children}</>;
}
