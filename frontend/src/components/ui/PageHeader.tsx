import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";

interface PageHeaderProps {
  title: string;
  /** Concise engineering description shown under the title. */
  description?: ReactNode;
  /** Small count / summary line (e.g. "14 of 46 substations"). */
  meta?: ReactNode;
  /** Primary + secondary actions, right-aligned on desktop. */
  actions?: ReactNode;
}

/**
 * Consistent page/workspace header for a module surface: an <h1>, a quiet
 * description, an optional result-count line, and an actions slot. No
 * decorative hero (Registry landing §6). Reused across the registry list,
 * create and detail workspaces so their headers cannot drift.
 */
export function PageHeader({ title, description, meta, actions }: PageHeaderProps) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: tokens.space[4],
        flexWrap: "wrap",
        marginBottom: tokens.space[5],
      }}
    >
      <div style={{ flex: "1 1 320px", minWidth: 0 }}>
        <h1
          style={{
            margin: 0,
            fontFamily: tokens.typography.fontFamily,
            fontSize: "22px",
            fontWeight: tokens.typography.weight.bold,
            letterSpacing: "-0.2px",
            color: tokens.color.textPrimary,
          }}
        >
          {title}
        </h1>
        {description != null && (
          <p
            style={{
              margin: `${tokens.space[2]} 0 0`,
              maxWidth: "70ch",
              fontFamily: tokens.typography.fontFamily,
              fontSize: tokens.typography.size.subhead,
              lineHeight: tokens.typography.lineHeight.normal,
              color: tokens.color.textSecondary,
            }}
          >
            {description}
          </p>
        )}
        {meta != null && (
          <p
            style={{
              margin: `${tokens.space[3]} 0 0`,
              fontFamily: tokens.typography.fontFamily,
              fontSize: tokens.typography.size.small,
              color: tokens.color.textSecondary,
            }}
          >
            {meta}
          </p>
        )}
      </div>
      {actions != null && (
        <div style={{ display: "flex", alignItems: "center", gap: tokens.space[2], flexWrap: "wrap" }}>{actions}</div>
      )}
    </header>
  );
}
