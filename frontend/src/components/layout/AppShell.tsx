import type { PropsWithChildren } from "react";

/**
 * Outermost page frame. Business-module navigation is added here once
 * modules exist (CLAUDE.md §15 — the frontend presents; it does not decide).
 */
export function AppShell({ children }: PropsWithChildren) {
  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <header style={{ padding: "1rem 1.5rem", borderBottom: "1px solid #e2e2e2" }}>
        <strong>GridDefence</strong>
      </header>
      <main style={{ flex: 1, padding: "1.5rem" }}>{children}</main>
    </div>
  );
}
