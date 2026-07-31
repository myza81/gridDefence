import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";

import { NAVIGATION, isGroupActive } from "../../app/navigation";
import { tokens } from "../../theme/tokens";
import { SidebarSection } from "./SidebarSection";

/** Ids of groups that contain the active route — kept open automatically. */
function activeGroupIds(pathname: string): string[] {
  const ids: string[] = [];
  for (const section of NAVIGATION) {
    for (const item of section.items) {
      if (item.children && isGroupActive(item, pathname)) ids.push(item.id);
    }
  }
  return ids;
}

interface AppSidebarProps {
  /** Desktop icon-rail mode. Always false inside the mobile drawer. */
  collapsed?: boolean;
  /** Un-collapse the rail (used when a collapsed group is clicked). */
  onRequestExpand?: () => void;
  /** Called after a destination link is followed (mobile drawer closes). */
  onNavigate?: () => void;
}

/**
 * The navigation body — a list of grouped engineering domains rendered from the
 * shared taxonomy (../../app/navigation.ts). Used both as the persistent
 * desktop sidebar and as the content of the mobile drawer, so navigation is
 * defined once and cannot diverge between the two.
 */
export function AppSidebar({ collapsed = false, onRequestExpand, onNavigate }: AppSidebarProps) {
  const { pathname } = useLocation();
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => new Set(activeGroupIds(pathname)));

  // Keep the group that owns the current route open as the engineer navigates.
  useEffect(() => {
    setExpandedGroups((current) => {
      const next = new Set(current);
      for (const id of activeGroupIds(pathname)) next.add(id);
      return next;
    });
  }, [pathname]);

  const toggleGroup = (groupId: string) => {
    setExpandedGroups((current) => {
      const next = new Set(current);
      if (next.has(groupId)) next.delete(groupId);
      else next.add(groupId);
      return next;
    });
  };

  return (
    <nav
      aria-label="Primary"
      style={{
        height: "100%",
        overflowY: "auto",
        overflowX: "hidden",
        padding: collapsed ? "10px 8px" : "10px 12px",
        display: "flex",
        flexDirection: "column",
        gap: "2px",
        background: tokens.color.surfacePanel,
      }}
    >
      {NAVIGATION.map((section) => (
        <SidebarSection
          key={section.id}
          section={section}
          collapsed={collapsed}
          pathname={pathname}
          expandedGroups={expandedGroups}
          onToggleGroup={toggleGroup}
          onRequestExpand={onRequestExpand}
          onNavigate={onNavigate}
        />
      ))}
    </nav>
  );
}
