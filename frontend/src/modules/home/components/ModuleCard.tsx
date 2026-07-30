import { useState } from "react";
import { Link } from "react-router-dom";

import { Card } from "../../../components/ui/Card";
import { tokens } from "../../../theme/tokens";
import type { EngineeringModule } from "../types";
import { HomeIcon } from "./HomeIcon";

/**
 * An engineering-domain entry card (icon, title, description). Navigates to the
 * module when a route exists; modules without a frontend route yet render as a
 * non-interactive "Coming soon" tile rather than a dead link.
 */
export function ModuleCard({ module }: { module: EngineeringModule }) {
  const [hover, setHover] = useState(false);
  const available = module.to !== undefined;

  const inner = (
    <Card interactive={available} hovered={hover} style={{ height: "100%", opacity: available ? 1 : 0.75 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: tokens.space[2], height: "100%" }}>
        <div style={{ display: "flex", alignItems: "center", gap: tokens.space[3] }}>
          <span
            style={{
              width: 34,
              height: 34,
              flex: "none",
              borderRadius: tokens.radius.md,
              backgroundColor: tokens.color.primaryWash,
              color: tokens.color.actionPrimary,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <HomeIcon name={module.icon} size={18} />
          </span>
          <span style={{ fontSize: "13.5px", fontWeight: tokens.typography.weight.bold, color: tokens.color.textPrimary }}>
            {module.title}
          </span>
          {!available && (
            <span style={{ marginLeft: "auto", fontSize: "10px", fontWeight: tokens.typography.weight.bold, textTransform: "uppercase", letterSpacing: "0.04em", color: tokens.color.textSecondary, border: `1px solid ${tokens.color.borderDefault}`, borderRadius: tokens.radius.sm, padding: "1px 6px" }}>
              Coming soon
            </span>
          )}
        </div>
        <p style={{ margin: 0, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
          {module.description}
        </p>
      </div>
    </Card>
  );

  if (!available) return inner;
  return (
    <Link
      to={module.to as string}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{ textDecoration: "none", display: "block", height: "100%" }}
    >
      {inner}
    </Link>
  );
}
