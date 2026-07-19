import type { SchemeVersionLifecycleStatus } from "./types";

interface LifecycleBadgeProps {
  status: SchemeVersionLifecycleStatus;
}

const LABELS: Record<SchemeVersionLifecycleStatus, string> = {
  DRAFT: "Draft",
  PUBLISHED: "Published",
  SUPERSEDED: "Superseded",
  ENTERED_IN_ERROR: "Entered in Error",
};

const COLORS: Record<SchemeVersionLifecycleStatus, string> = {
  DRAFT: "#6e7781",
  PUBLISHED: "#1a7f37",
  SUPERSEDED: "#9a6700",
  ENTERED_IN_ERROR: "#cf222e",
};

/**
 * Displays a Defence Scheme Version's lifecycle status (ADR-015's own
 * four-state model — Draft, Published, Superseded, Entered in Error).
 * Scheme-agnostic: never references UFLS, UVLS, or EMLS. A future
 * concrete scheme module reuses this directly.
 */
export function LifecycleBadge({ status }: LifecycleBadgeProps) {
  return (
    <span
      data-testid="lifecycle-badge"
      style={{
        display: "inline-block",
        padding: "0.15rem 0.6rem",
        borderRadius: "999px",
        fontSize: "0.85rem",
        color: "white",
        backgroundColor: COLORS[status],
      }}
    >
      {LABELS[status]}
    </span>
  );
}
