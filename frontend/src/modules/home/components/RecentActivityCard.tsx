import { Card } from "../../../components/ui/Card";
import { tokens } from "../../../theme/tokens";
import type { ActivityItem } from "../types";
import { HomeIcon } from "./HomeIcon";

/**
 * Recent engineering activity — a simple, read-only timeline (mock-driven).
 * Not analytics; just what has recently happened, for situational continuity.
 */
export function RecentActivityCard({ items }: { items: ActivityItem[] }) {
  return (
    <Card padding={tokens.space[2]}>
      {items.map((item, i) => (
        <div
          key={item.id}
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: tokens.space[3],
            padding: tokens.space[3],
            borderBottom: i === items.length - 1 ? "none" : `1px solid ${tokens.color.borderDefault}`,
          }}
        >
          <span
            style={{
              width: 28,
              height: 28,
              flex: "none",
              borderRadius: tokens.radius.sm,
              backgroundColor: tokens.color.surfaceSubtle,
              color: tokens.color.fieldIcon,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <HomeIcon name={item.icon} size={15} />
          </span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: "12.5px", fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>{item.title}</div>
            <div style={{ fontSize: "11px", color: tokens.color.textSecondary, marginTop: 1 }}>{item.meta}</div>
          </div>
        </div>
      ))}
    </Card>
  );
}
