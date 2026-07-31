import { Link } from "react-router-dom";

import type { NavItem } from "../../app/navigation";
import { isGroupActive, isRouteActive } from "../../app/navigation";
import { tokens } from "../../theme/tokens";
import { NavIcon } from "./NavIcon";

const rowBase = {
  position: "relative",
  display: "flex",
  alignItems: "center",
  gap: tokens.space[2],
  padding: "7px 10px",
  borderRadius: tokens.radius.sm,
  fontFamily: tokens.typography.fontFamily,
  fontSize: "13px",
  fontWeight: tokens.typography.weight.medium,
  color: tokens.color.textPrimary,
  textDecoration: "none",
  width: "100%",
  boxSizing: "border-box",
  border: "none",
  background: "transparent",
  cursor: "pointer",
  textAlign: "left",
} as const;

function activeAccent() {
  return (
    <span
      aria-hidden="true"
      style={{
        position: "absolute",
        left: "-12px",
        top: "6px",
        bottom: "6px",
        width: "3px",
        borderRadius: "0 3px 3px 0",
        background: tokens.color.actionPrimary,
      }}
    />
  );
}

/** Shrinks/centres a row when the desktop sidebar is collapsed to the icon rail. */
function collapsedRowStyle(collapsed: boolean) {
  return collapsed ? { justifyContent: "center", padding: "9px 0" } : {};
}

interface LeafProps {
  item: NavItem;
  collapsed: boolean;
  pathname: string;
  /** Nested one level under a group parent (smaller, no icon column). */
  nested?: boolean;
  onNavigate?: () => void;
}

/** A routed destination, or a clearly-inactive "coming soon" entry (never a dead link). */
export function SidebarLeaf({ item, collapsed, pathname, nested = false, onNavigate }: LeafProps) {
  const label = item.label;

  if (item.availability === "coming-soon" || !item.route) {
    // Non-interactive: not a link, not focusable as a destination.
    if (collapsed) {
      return (
        <span
          title={`${label} — coming soon`}
          aria-label={`${label}, coming soon`}
          style={{ ...rowBase, ...collapsedRowStyle(true), color: tokens.color.textFaint, cursor: "default" }}
        >
          {item.icon && <NavIcon name={item.icon} />}
        </span>
      );
    }
    return (
      <span
        aria-disabled="true"
        title={`${label} — coming soon`}
        style={{ ...rowBase, color: tokens.color.textFaint, cursor: "default", fontWeight: nested ? tokens.typography.weight.regular : tokens.typography.weight.medium, ...(nested ? { paddingLeft: "10px", fontSize: "12.5px" } : {}) }}
      >
        {!nested && item.icon && <NavIcon name={item.icon} />}
        <span style={{ flex: 1 }}>{label}</span>
        <span style={comingSoonTag}>Soon</span>
      </span>
    );
  }

  const active = isRouteActive(item.route, pathname);
  const style = {
    ...rowBase,
    ...collapsedRowStyle(collapsed),
    ...(nested && !collapsed ? { paddingLeft: "10px", fontSize: "12.5px", fontWeight: tokens.typography.weight.medium } : {}),
    ...(active
      ? {
          background: tokens.color.primaryWash,
          color: tokens.color.actionPrimaryHover,
          fontWeight: tokens.typography.weight.semibold,
        }
      : {}),
  };

  return (
    <Link
      to={item.route}
      aria-current={active ? "page" : undefined}
      title={collapsed ? label : undefined}
      aria-label={collapsed ? label : undefined}
      onClick={onNavigate}
      style={style}
      data-testid={`nav-${item.id}`}
    >
      {active && !collapsed && activeAccent()}
      {(!nested || collapsed) && item.icon && (
        <span style={{ color: active ? tokens.color.actionPrimary : tokens.color.textSecondary, display: "flex" }}>
          <NavIcon name={item.icon} />
        </span>
      )}
      {!collapsed && <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{label}</span>}
    </Link>
  );
}

interface GroupProps {
  item: NavItem;
  collapsed: boolean;
  pathname: string;
  expanded: boolean;
  onToggle: () => void;
  /** Collapsed rail: clicking a group re-expands the sidebar rather than nesting a flyout. */
  onRequestExpand?: () => void;
  onNavigate?: () => void;
}

/** An expandable domain group; highlights when any descendant route is active. */
export function SidebarGroup({ item, collapsed, pathname, expanded, onToggle, onRequestExpand, onNavigate }: GroupProps) {
  const groupActive = isGroupActive(item, pathname);
  const showChildren = expanded && !collapsed;

  const headerStyle = {
    ...rowBase,
    ...collapsedRowStyle(collapsed),
    ...(groupActive
      ? { background: collapsed ? tokens.color.primaryWash : "transparent", color: tokens.color.actionPrimaryHover, fontWeight: tokens.typography.weight.semibold }
      : {}),
  };

  return (
    <div>
      <button
        type="button"
        aria-expanded={collapsed ? undefined : expanded}
        aria-label={collapsed ? `${item.label}${groupActive ? ", contains current page" : ""}` : undefined}
        title={collapsed ? item.label : undefined}
        onClick={() => {
          if (collapsed) {
            onRequestExpand?.();
            if (!expanded) onToggle();
            return;
          }
          onToggle();
        }}
        style={headerStyle}
      >
        {groupActive && collapsed && activeAccent()}
        {item.icon && (
          <span style={{ color: groupActive ? tokens.color.actionPrimary : tokens.color.textSecondary, display: "flex" }}>
            <NavIcon name={item.icon} />
          </span>
        )}
        {!collapsed && <span style={{ flex: 1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{item.label}</span>}
        {!collapsed && (
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke={tokens.color.textFaint}
            strokeWidth="2"
            aria-hidden="true"
            style={{ transform: expanded ? "rotate(0deg)" : "rotate(-90deg)", transition: `transform ${tokens.transition.base}` }}
          >
            <path d="m6 9 6 6 6-6" strokeLinecap="round" />
          </svg>
        )}
      </button>

      {showChildren && (
        <div
          style={{
            margin: "2px 0 4px 15px",
            borderLeft: `1px solid ${tokens.color.borderDivider}`,
            paddingLeft: "9px",
            display: "flex",
            flexDirection: "column",
            gap: "1px",
          }}
        >
          {item.children?.map((child) => (
            <SidebarLeaf key={child.id} item={child} collapsed={false} pathname={pathname} nested onNavigate={onNavigate} />
          ))}
        </div>
      )}
    </div>
  );
}

const comingSoonTag = {
  flex: "none",
  fontSize: "9.5px",
  fontWeight: tokens.typography.weight.semibold,
  letterSpacing: "0.04em",
  textTransform: "uppercase",
  color: tokens.color.textFaint,
  border: `1px solid ${tokens.color.borderDefault}`,
  borderRadius: "4px",
  padding: "0 5px",
} as const;
