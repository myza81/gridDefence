import type { PropsWithChildren } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../../modules/iam/AuthContext";

/**
 * Outermost page frame. Business-module navigation is added here once
 * modules exist (CLAUDE.md §15 — the frontend presents; it does not decide).
 */
export function AppShell({ children }: PropsWithChildren) {
  const { token, currentUser, logout } = useAuth();

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header
        style={{
          padding: "1rem 1.5rem",
          borderBottom: "1px solid #e2e2e2",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <strong>GridDefence</strong>
          {token !== null && (
            <nav style={{ display: "inline-flex", gap: "1rem", marginLeft: "1.5rem" }}>
              <Link to="/">Status</Link>
              <Link to="/substations">Substations</Link>
              <Link to="/circuits">Circuits</Link>
              <Link to="/transformers">Transformers</Link>
              <Link to="/automatic-load-shedding-functionality">ALSF Registry</Link>
              <Link to="/psse-integration/import">PSS/E Import</Link>
              <Link to="/psse-integration/history">PSS/E History</Link>
              <Link to="/psse-integration/current-status">PSS/E Status</Link>
              <Link to="/network-model">Network Explorer</Link>
              <Link to="/network-model/substations">Network Substations</Link>
              <Link to="/network-model/traversal">Network Traversal</Link>
              <Link to="/network-model/verification">Snapshot Verification</Link>
              <Link to="/users">Users</Link>
              <Link to="/roles">Roles</Link>
              <Link to="/permissions">Permissions</Link>
            </nav>
          )}
        </div>
        {token !== null && (
          <div data-testid="current-user-display">
            {currentUser ? `Signed in as ${currentUser.username}` : "Loading..."}
            <button type="button" onClick={() => void logout()} style={{ marginLeft: "0.75rem" }}>
              Sign out
            </button>
          </div>
        )}
      </header>
      <main style={{ flex: 1, padding: "1.5rem" }}>{children}</main>
    </div>
  );
}
