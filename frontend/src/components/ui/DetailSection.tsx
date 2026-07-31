import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";
import { Card } from "./Card";

interface DetailSectionProps {
  title: string;
  /** Quiet supporting sentence under the heading. */
  description?: ReactNode;
  /** Right-aligned section actions (e.g. an "Edit" / lifecycle action). */
  actions?: ReactNode;
  children: ReactNode;
  /** Heading level for the section title (default h2). */
  headingLevel?: 2 | 3;
}

/**
 * A titled card section for the detail workspace (Detail workspace §10), so the
 * record reads as grouped engineering sections (Identity, Classification,
 * Lifecycle, …) rather than one flat form or a raw JSON dump.
 */
export function DetailSection({ title, description, actions, children, headingLevel = 2 }: DetailSectionProps) {
  const Heading = headingLevel === 3 ? "h3" : "h2";
  return (
    <Card padding={tokens.space[5]} style={{ display: "flex", flexDirection: "column", gap: tokens.space[4] }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: tokens.space[3], flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 auto", minWidth: 0 }}>
          <Heading
            style={{
              margin: 0,
              fontFamily: tokens.typography.fontFamily,
              fontSize: "15px",
              fontWeight: tokens.typography.weight.bold,
              letterSpacing: "0.01em",
              color: tokens.color.textPrimary,
            }}
          >
            {title}
          </Heading>
          {description != null && (
            <p style={{ margin: `${tokens.space[1]} 0 0`, fontFamily: tokens.typography.fontFamily, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
              {description}
            </p>
          )}
        </div>
        {actions != null && <div style={{ display: "flex", gap: tokens.space[2], flexWrap: "wrap" }}>{actions}</div>}
      </div>
      {children}
    </Card>
  );
}
