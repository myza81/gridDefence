import { useState } from "react";
import { Link } from "react-router-dom";

import { Card } from "../../../components/ui/Card";
import { tokens } from "../../../theme/tokens";
import type { ContinueWorkingItem } from "../types";
import { HomeIcon } from "./HomeIcon";

function WorkRow({ item, isLast }: { item: ContinueWorkingItem; isLast: boolean }) {
  const [hover, setHover] = useState(false);
  return (
    <Link
      to={item.to}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: tokens.space[3],
        padding: tokens.space[3],
        borderRadius: tokens.radius.sm,
        borderBottom: isLast ? "none" : `1px solid ${tokens.color.borderDefault}`,
        textDecoration: "none",
        backgroundColor: hover ? tokens.color.surfaceSubtle : "transparent",
      }}
    >
      <span style={{ display: "inline-flex", color: tokens.color.fieldIcon }}>
        <HomeIcon name={item.icon} size={17} />
      </span>
      <span style={{ flex: 1, minWidth: 0 }}>
        <span style={{ display: "block", fontSize: "12.5px", fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>
          {item.title}
        </span>
        {item.meta !== undefined && (
          <span style={{ display: "block", fontSize: "11px", color: tokens.color.textSecondary }}>{item.meta}</span>
        )}
      </span>
      <span aria-hidden="true" style={{ color: tokens.color.link, fontWeight: tokens.typography.weight.bold, fontSize: 12 }}>›</span>
    </Link>
  );
}

/** Card listing recently accessed engineering work — resume points, each clickable. */
export function ContinueWorkingCard({ items }: { items: ContinueWorkingItem[] }) {
  return (
    <Card padding={tokens.space[2]}>
      {items.map((item, i) => (
        <WorkRow key={item.id} item={item} isLast={i === items.length - 1} />
      ))}
    </Card>
  );
}
