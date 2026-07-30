import { tokens } from "../../../theme/tokens";

function greetingFor(hour: number): string {
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

interface WelcomePanelProps {
  /** Display name of the signed-in engineer (from AuthContext). */
  userName: string;
  now?: Date;
}

/**
 * Restrained welcome header — greeting, engineer name, and platform identity.
 * No oversized hero banner; this orients the engineer, it does not market.
 */
export function WelcomePanel({ userName, now = new Date() }: WelcomePanelProps) {
  const dateLabel = now.toLocaleDateString(undefined, {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const timeLabel = now.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });

  return (
    <div
      style={{
        display: "flex",
        alignItems: "flex-end",
        justifyContent: "space-between",
        gap: tokens.space[4],
        flexWrap: "wrap",
      }}
    >
      <div>
        <p style={{ margin: 0, fontSize: tokens.typography.size.small, fontWeight: tokens.typography.weight.semibold, color: tokens.color.link, letterSpacing: "0.02em" }}>
          {greetingFor(now.getHours())}
        </p>
        <h1
          style={{
            margin: "4px 0 2px",
            fontFamily: tokens.typography.fontFamily,
            fontSize: "1.6rem",
            fontWeight: tokens.typography.weight.bold,
            color: tokens.color.textPrimary,
            letterSpacing: "-0.3px",
          }}
        >
          Welcome back, {userName}
        </h1>
        <p style={{ margin: 0, fontSize: tokens.typography.size.subhead, color: tokens.color.textSecondary }}>
          GridDefence · Transmission Grid Defence Engineering Platform
        </p>
      </div>
      <div style={{ textAlign: "right", color: tokens.color.textSecondary, fontSize: tokens.typography.size.small }}>
        <div style={{ fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary }}>{timeLabel}</div>
        <div>{dateLabel}</div>
      </div>
    </div>
  );
}
