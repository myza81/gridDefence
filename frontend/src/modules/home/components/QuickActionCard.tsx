import { useState } from "react";
import { Link } from "react-router-dom";

import { tokens } from "../../../theme/tokens";
import type { QuickAction } from "../types";
import { HomeIcon } from "./HomeIcon";

/**
 * A single reusable quick-action — an engineering task the engineer starts
 * directly from Home. Rendered as a navigating Link styled in the shared
 * button language (primary for the most common action, else secondary).
 */
export function QuickActionCard({ action }: { action: QuickAction }) {
  const [hover, setHover] = useState(false);
  const primary = action.primary === true;

  return (
    <Link
      to={action.to}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: tokens.space[3],
        height: "44px",
        padding: `0 ${tokens.space[4]}`,
        borderRadius: tokens.radius.md,
        textDecoration: "none",
        fontFamily: tokens.typography.fontFamily,
        fontSize: tokens.typography.size.button,
        fontWeight: tokens.typography.weight.semibold,
        border: `1px solid ${primary ? tokens.color.actionPrimary : tokens.color.borderStrong}`,
        backgroundColor: primary
          ? hover
            ? tokens.color.actionPrimaryHover
            : tokens.color.actionPrimary
          : hover
            ? tokens.color.surfaceSubtle
            : tokens.color.surfacePanel,
        color: primary ? tokens.color.actionPrimaryText : tokens.color.textPrimary,
        transition: `background-color ${tokens.transition.base}, border-color ${tokens.transition.base}`,
        boxSizing: "border-box",
      }}
    >
      <span style={{ display: "inline-flex", color: primary ? tokens.color.actionPrimaryText : tokens.color.actionPrimary }}>
        <HomeIcon name={action.icon} size={17} />
      </span>
      {action.label}
    </Link>
  );
}
