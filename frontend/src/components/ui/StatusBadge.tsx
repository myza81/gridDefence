interface StatusBadgeProps {
  label: string;
  tone?: "ok" | "error" | "pending";
}

/**
 * Minimal reusable UI primitive — a placeholder demonstrating the
 * components/ui convention future modules build on. Not a design system;
 * that is a later decision, not a Phase 0 one.
 */
export function StatusBadge({ label, tone = "pending" }: StatusBadgeProps) {
  const colors: Record<typeof tone, string> = {
    ok: "#1a7f37",
    error: "#cf222e",
    pending: "#6e7781",
  };

  return (
    <span
      data-testid="status-badge"
      style={{
        display: "inline-block",
        padding: "0.15rem 0.6rem",
        borderRadius: "999px",
        fontSize: "0.85rem",
        color: "white",
        backgroundColor: colors[tone],
      }}
    >
      {label}
    </span>
  );
}
