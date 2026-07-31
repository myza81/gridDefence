import type { PropsWithChildren } from "react";
import { useEffect, useState } from "react";

import { tokens } from "../../theme/tokens";
import { AppHeader } from "./AppHeader";
import { AppSidebar } from "./AppSidebar";
import { Breadcrumbs } from "./Breadcrumbs";
import { MobileNavigationDrawer } from "./MobileNavigationDrawer";
import { useIsMobile } from "./useIsMobile";

/**
 * GridDefence Application Shell V2 — the permanent authenticated frame every
 * engineering workspace runs inside (docs/architecture/application-shell-architecture.md).
 *
 * ROLE COMPOSITION, NOT A MONOLITH: this component only orchestrates the shell
 * roles and owns the little state that spans them (rail collapse, drawer open,
 * viewport class). Each role lives in its own small component —
 *   AppHeader  → global-frame role (identity, search, awareness, user)
 *   AppSidebar → navigation role (shared taxonomy)
 *   Breadcrumbs→ active-context / orientation role
 *   <main>     → workspace host (renders the routed page)
 * — so the shell can grow by composition without this file growing (§8, §16).
 *
 * DELIBERATE OMISSIONS (honesty over visual completeness): the approved mockup
 * shows an engineering-scope band (selected snapshot/scheme) and an
 * ambient-status bar (live counts, import %). Those imply engineering state
 * that does not exist yet; per Application Shell Architecture §3/§7 and
 * Navigation Architecture §16 the shell must not fabricate scope or awareness,
 * so both are left out until real state backs them. The breadcrumb row honestly
 * fills the active-context band.
 */
export function AppShell({ children }: PropsWithChildren) {
  const isMobile = useIsMobile();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Never leave the mobile drawer mounted once we are back on a desktop layout.
  useEffect(() => {
    if (!isMobile && drawerOpen) setDrawerOpen(false);
  }, [isMobile, drawerOpen]);

  const sidebarWidth = collapsed ? tokens.layout.sidebarCollapsedWidth : tokens.layout.sidebarWidth;

  return (
    <div
      style={{
        height: "100dvh",
        display: "grid",
        gridTemplateRows: `${tokens.layout.headerHeight} 1fr`,
        gridTemplateColumns: isMobile ? "1fr" : `${sidebarWidth} 1fr`,
        gridTemplateAreas: isMobile ? `"header" "main"` : `"header header" "sidebar main"`,
        background: tokens.color.canvas,
        overflow: "hidden",
      }}
    >
      <AppHeader
        isMobile={isMobile}
        collapsed={collapsed}
        onToggleSidebar={() => setCollapsed((value) => !value)}
        onOpenDrawer={() => setDrawerOpen(true)}
      />

      {!isMobile && (
        <aside
          style={{
            gridArea: "sidebar",
            minHeight: 0,
            borderRight: `1px solid ${tokens.color.borderDefault}`,
            background: tokens.color.surfacePanel,
            overflow: "hidden",
          }}
        >
          <AppSidebar collapsed={collapsed} onRequestExpand={() => setCollapsed(false)} />
        </aside>
      )}

      <div style={{ gridArea: "main", minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <div
          style={{
            flex: "none",
            display: "flex",
            alignItems: "center",
            gap: tokens.space[3],
            padding: "8px 20px",
            background: tokens.color.surfaceSubtle,
            borderBottom: `1px solid ${tokens.color.borderDefault}`,
          }}
        >
          <Breadcrumbs />
        </div>

        <main style={{ flex: 1, minHeight: 0, overflowY: "auto", overflowX: "hidden", padding: tokens.space[6] }}>
          {children}
        </main>
      </div>

      {isMobile && <MobileNavigationDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />}
    </div>
  );
}
