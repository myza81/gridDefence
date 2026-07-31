import type { NavSection } from "../../app/navigation";
import { tokens } from "../../theme/tokens";
import { SidebarGroup, SidebarLeaf } from "./SidebarItem";

interface SidebarSectionProps {
  section: NavSection;
  collapsed: boolean;
  pathname: string;
  expandedGroups: Set<string>;
  onToggleGroup: (groupId: string) => void;
  onRequestExpand?: () => void;
  onNavigate?: () => void;
}

/** One labelled navigation group ("Engineering Domains", "System", …). */
export function SidebarSection({
  section,
  collapsed,
  pathname,
  expandedGroups,
  onToggleGroup,
  onRequestExpand,
  onNavigate,
}: SidebarSectionProps) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1px" }}>
      {section.label && !collapsed && (
        <div
          style={{
            fontFamily: tokens.typography.fontFamily,
            fontSize: "10px",
            letterSpacing: "0.11em",
            textTransform: "uppercase",
            color: tokens.color.textFaint,
            fontWeight: tokens.typography.weight.bold,
            padding: "12px 10px 5px",
          }}
        >
          {section.label}
        </div>
      )}
      {section.label && collapsed && (
        // Keep visual separation between rail sections without the text label.
        <div aria-hidden="true" style={{ height: "1px", background: tokens.color.borderDivider, margin: "8px 8px 6px" }} />
      )}

      {section.items.map((item) =>
        item.children ? (
          <SidebarGroup
            key={item.id}
            item={item}
            collapsed={collapsed}
            pathname={pathname}
            expanded={expandedGroups.has(item.id)}
            onToggle={() => onToggleGroup(item.id)}
            onRequestExpand={onRequestExpand}
            onNavigate={onNavigate}
          />
        ) : (
          <SidebarLeaf key={item.id} item={item} collapsed={collapsed} pathname={pathname} onNavigate={onNavigate} />
        ),
      )}
    </div>
  );
}
