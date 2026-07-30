import { useState } from "react";
import { Link } from "react-router-dom";

import { Card } from "../../../components/ui/Card";
import { tokens } from "../../../theme/tokens";
import type { AttentionItem, AttentionTone } from "../types";

const TONE: Record<AttentionTone, { color: string; marker: React.ReactNode; word: string }> = {
  critical: { color: "#C2410C", word: "Critical", marker: <rect x="1" y="1" width="10" height="10" rx="2" /> },
  warning: { color: "#B5730E", word: "Warning", marker: <path d="M6 1 11 11 H1 Z" /> },
  info: { color: "#2560E6", word: "Info", marker: <circle cx="6" cy="6" r="5" /> },
  ok: { color: "#1F8A54", word: "OK", marker: <circle cx="6" cy="6" r="5" /> },
};

function ToneMarker({ tone }: { tone: AttentionTone }) {
  const t = TONE[tone];
  return (
    <svg width="12" height="12" viewBox="0 0 12 12" fill={t.color} aria-hidden="true" style={{ flex: "none", marginTop: 3 }}>
      {t.marker}
    </svg>
  );
}

function AttentionRow({ item, isLast }: { item: AttentionItem; isLast: boolean }) {
  const [hover, setHover] = useState(false);
  const body = (
    <div
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: tokens.space[3],
        padding: `${tokens.space[3]} ${tokens.space[3]}`,
        borderRadius: tokens.radius.sm,
        borderBottom: isLast ? "none" : `1px solid ${tokens.color.borderDefault}`,
        backgroundColor: hover && item.to !== undefined ? tokens.color.surfaceSubtle : "transparent",
      }}
    >
      <ToneMarker tone={item.tone} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: "12.5px", fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>
          <span style={{ color: TONE[item.tone].color, fontSize: "10px", fontWeight: tokens.typography.weight.bold, textTransform: "uppercase", letterSpacing: "0.04em", marginRight: 8 }}>
            {TONE[item.tone].word}
          </span>
          {item.label}
        </div>
        {item.detail !== undefined && (
          <div style={{ fontSize: tokens.typography.size.small, color: tokens.color.textSecondary, marginTop: 2 }}>{item.detail}</div>
        )}
      </div>
      {item.to !== undefined && (
        <span aria-hidden="true" style={{ color: tokens.color.link, fontWeight: tokens.typography.weight.bold, fontSize: 12 }}>›</span>
      )}
    </div>
  );

  if (item.to === undefined) return body;
  return (
    <Link
      to={item.to}
      style={{ textDecoration: "none", display: "block" }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {body}
    </Link>
  );
}

/** Card of engineering items requiring attention (design-only, mock-driven). */
export function AttentionCard({ items }: { items: AttentionItem[] }) {
  return (
    <Card padding={tokens.space[2]}>
      {items.map((item, i) => (
        <AttentionRow key={item.id} item={item} isLast={i === items.length - 1} />
      ))}
    </Card>
  );
}
