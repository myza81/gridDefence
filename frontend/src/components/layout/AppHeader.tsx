import { tokens } from "../../theme/tokens";
import { BrandMark } from "./BrandMark";
import { GlobalSearchPlaceholder } from "./GlobalSearchPlaceholder";
import { NotificationControl } from "./NotificationControl";
import { UserMenu } from "./UserMenu";

interface AppHeaderProps {
  isMobile: boolean;
  collapsed: boolean;
  /** Desktop: toggle the icon rail. */
  onToggleSidebar: () => void;
  /** Mobile: open the navigation drawer. */
  onOpenDrawer: () => void;
}

/**
 * The global-frame role (Application Shell Architecture §2): identity, global
 * discovery (search placeholder), global awareness (notifications) and the user
 * menu. Kept visually quiet (Header §5) — it does not restate the sidebar and
 * carries no page title (page headings live in page content).
 */
export function AppHeader({ isMobile, collapsed, onToggleSidebar, onOpenDrawer }: AppHeaderProps) {
  return (
    <header
      style={{
        gridArea: "header",
        display: "flex",
        alignItems: "center",
        gap: tokens.space[4],
        height: tokens.layout.headerHeight,
        padding: "0 14px",
        background: tokens.color.surfacePanel,
        borderBottom: `1px solid ${tokens.color.borderDefault}`,
        boxShadow: tokens.shadow.hairline,
      }}
    >
      <button
        type="button"
        onClick={isMobile ? onOpenDrawer : onToggleSidebar}
        aria-label={isMobile ? "Open navigation" : collapsed ? "Expand sidebar" : "Collapse sidebar"}
        aria-expanded={isMobile ? undefined : !collapsed}
        style={{
          width: "36px",
          height: "36px",
          flex: "none",
          borderRadius: tokens.radius.sm,
          border: "1px solid transparent",
          background: "transparent",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: tokens.color.textPrimary,
          cursor: "pointer",
        }}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" aria-hidden="true">
          <path d="M4 7h16M4 12h16M4 17h16" strokeLinecap="round" />
        </svg>
      </button>

      <BrandMark wordmark={!isMobile} />

      {!isMobile && <GlobalSearchPlaceholder />}

      <div style={{ flex: 1 }} />

      <div style={{ display: "flex", alignItems: "center", gap: tokens.space[2] }}>
        <NotificationControl />
        <div aria-hidden="true" style={{ width: "1px", height: "26px", background: tokens.color.borderDivider, margin: `0 ${tokens.space[1]}` }} />
        <UserMenu />
      </div>
    </header>
  );
}
