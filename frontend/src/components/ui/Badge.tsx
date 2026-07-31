import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";

export type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

interface BadgeProps {
  label: ReactNode;
  tone?: BadgeTone;
  /** Show a leading status dot (shape reinforces the tone beyond colour). */
  dot?: boolean;
}

/**
 * Soft, calm status pill for engineering state (tinted background + coloured
 * text + optional dot) — the shell/registry counterpart to the heavier
 * white-on-solid StatusBadge. Meaning is carried by the TEXT label; colour and
 * the dot only reinforce it (never colour alone — Accessibility §21).
 */
const PALETTE: Record<BadgeTone, { bg: string; fg: string; dot: string }> = {
  neutral: { bg: "#EEF1F6", fg: "#495468", dot: "#8B98AD" },
  info: { bg: tokens.color.primaryWash, fg: "#2039C4", dot: tokens.color.actionPrimary },
  success: { bg: "#E3F3EA", fg: "#1F8A54", dot: "#22A45D" },
  warning: { bg: "#FBF0DC", fg: "#8A5A00", dot: "#D9880F" },
  danger: { bg: "#FBE7E4", fg: "#B23A1B", dot: "#C2410C" },
};

export function Badge({ label, tone = "neutral", dot = true }: BadgeProps) {
  const colors = PALETTE[tone];
  return (
    <span
      data-testid="badge"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "2px 10px",
        borderRadius: tokens.radius.pill,
        background: colors.bg,
        color: colors.fg,
        fontFamily: tokens.typography.fontFamily,
        fontSize: "12px",
        fontWeight: tokens.typography.weight.semibold,
        lineHeight: 1.5,
        whiteSpace: "nowrap",
      }}
    >
      {dot && (
        <span aria-hidden="true" style={{ width: "7px", height: "7px", borderRadius: "50%", background: colors.dot, flex: "none" }} />
      )}
      {label}
    </span>
  );
}
