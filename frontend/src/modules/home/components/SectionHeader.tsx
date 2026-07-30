import { tokens } from "../../../theme/tokens";

interface SectionHeaderProps {
  title: string;
  description?: string;
  /** Optional trailing action (e.g. a "View all" link) aligned to the right. */
  action?: React.ReactNode;
}

/** Compact, consistent section title used between Home workspace sections. */
export function SectionHeader({ title, description, action }: SectionHeaderProps) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "baseline",
        gap: tokens.space[3],
        margin: `0 0 ${tokens.space[3]}`,
      }}
    >
      <div>
        <h2
          style={{
            margin: 0,
            fontFamily: tokens.typography.fontFamily,
            fontSize: "1.05rem",
            fontWeight: tokens.typography.weight.bold,
            color: tokens.color.textPrimary,
            letterSpacing: "-0.1px",
          }}
        >
          {title}
        </h2>
        {description !== undefined && (
          <p style={{ margin: `2px 0 0`, fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>
            {description}
          </p>
        )}
      </div>
      {action !== undefined && <div style={{ marginLeft: "auto" }}>{action}</div>}
    </div>
  );
}
