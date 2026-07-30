import type { CSSProperties, PropsWithChildren } from "react";

import { tokens } from "../../theme/tokens";

interface CardProps extends PropsWithChildren {
  /** Adds hover affordance + pointer cursor for whole-card links/buttons. */
  interactive?: boolean;
  hovered?: boolean;
  padding?: string;
  style?: CSSProperties;
}

/**
 * Generic white surface card built on the shared design tokens and the
 * repository's inline-style architecture (no stylesheet/className system).
 * Reused by the Engineering Home sections so they share one card chrome
 * (surface, border, radius, restrained elevation) rather than duplicating it.
 */
export function Card({ interactive = false, hovered = false, padding, children, style }: CardProps) {
  return (
    <div
      style={{
        backgroundColor: tokens.color.surfacePanel,
        border: `1px solid ${interactive && hovered ? tokens.color.borderStrong : tokens.color.borderDefault}`,
        borderRadius: tokens.radius.lg,
        boxShadow: interactive && hovered ? tokens.shadow.panel : "0 1px 2px rgba(15,30,61,0.04)",
        padding: padding ?? tokens.space[5],
        transition: `border-color ${tokens.transition.base}, box-shadow ${tokens.transition.base}`,
        boxSizing: "border-box",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
