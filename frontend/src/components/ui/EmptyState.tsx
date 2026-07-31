import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}

/**
 * Honest empty/blank state (Loading, empty and unavailable states §14). The
 * caller decides the message so "nothing registered" and "nothing matches the
 * filters" stay distinct — this component only renders it calmly.
 */
export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        textAlign: "center",
        gap: tokens.space[3],
        padding: `${tokens.space[10]} ${tokens.space[6]}`,
        border: `1px dashed ${tokens.color.borderStrong}`,
        borderRadius: tokens.radius.lg,
        background: tokens.color.surfaceSubtle,
        fontFamily: tokens.typography.fontFamily,
      }}
    >
      <p style={{ margin: 0, fontWeight: tokens.typography.weight.semibold, fontSize: tokens.typography.size.subhead, color: tokens.color.textPrimary }}>
        {title}
      </p>
      {description != null && (
        <p style={{ margin: 0, maxWidth: "48ch", fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
          {description}
        </p>
      )}
      {action}
    </div>
  );
}
