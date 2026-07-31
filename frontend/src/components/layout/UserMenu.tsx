import { useRef, useState } from "react";

import { tokens } from "../../theme/tokens";
import { useAuth } from "../../modules/iam/AuthContext";
import { useDismiss } from "./useDismiss";

/**
 * Header identity control. Reflects the authenticated user (owned by IAM,
 * CLAUDE.md F4) and exposes only actions that are real today: sign out.
 *
 * Profile and Preferences are intentionally OMITTED — no such routes exist, and
 * the brief forbids fabricating them (§8). A role line is likewise not shown:
 * AuthContext exposes a permission set, not a display role name, so inventing
 * one would misrepresent identity. Logout delegates to the existing, working
 * AuthContext.logout().
 */
export function UserMenu() {
  const { currentUser, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  useDismiss(open, containerRef, () => setOpen(false));

  const displayName = currentUser?.display_name ?? currentUser?.username ?? "Account";
  const secondary = currentUser?.username ? `@${currentUser.username}` : "Signed in";
  const initials = toInitials(displayName);

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Account menu for ${displayName}`}
        onClick={() => setOpen((value) => !value)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: tokens.space[2],
          padding: "4px 6px 4px 4px",
          borderRadius: tokens.radius.sm,
          border: "1px solid transparent",
          background: "transparent",
          cursor: "pointer",
          fontFamily: tokens.typography.fontFamily,
          maxWidth: "220px",
        }}
      >
        <span aria-hidden="true" style={avatarStyle}>
          {initials}
        </span>
        <span style={{ minWidth: 0, textAlign: "left", lineHeight: 1.15, display: "flex", flexDirection: "column" }}>
          <span
            style={{
              fontWeight: tokens.typography.weight.semibold,
              fontSize: "12.5px",
              color: tokens.color.textPrimary,
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {displayName}
          </span>
          <span style={{ fontSize: "11px", color: tokens.color.textSecondary, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {secondary}
          </span>
        </span>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={tokens.color.textFaint} strokeWidth="2" aria-hidden="true" style={{ flex: "none" }}>
          <path d="m6 9 6 6 6-6" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Account"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: "232px",
            maxWidth: "calc(100vw - 24px)",
            background: tokens.color.surfacePanel,
            border: `1px solid ${tokens.color.borderDefault}`,
            borderRadius: tokens.radius.md,
            boxShadow: tokens.shadow.panel,
            padding: tokens.space[2],
            zIndex: 60,
            fontFamily: tokens.typography.fontFamily,
          }}
        >
          <div style={{ padding: `${tokens.space[2]} ${tokens.space[3]}`, borderBottom: `1px solid ${tokens.color.borderDivider}`, marginBottom: tokens.space[2] }}>
            <div style={{ fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary, fontSize: tokens.typography.size.label }}>
              {displayName}
            </div>
            <div style={{ fontSize: tokens.typography.size.small, color: tokens.color.textSecondary }}>{secondary}</div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              void logout();
            }}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: tokens.space[2],
              padding: `${tokens.space[2]} ${tokens.space[3]}`,
              borderRadius: tokens.radius.sm,
              border: "none",
              background: "transparent",
              color: tokens.color.textPrimary,
              fontFamily: tokens.typography.fontFamily,
              fontSize: tokens.typography.size.label,
              fontWeight: tokens.typography.weight.medium,
              textAlign: "left",
              cursor: "pointer",
            }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
              <path d="M15 4h3a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-3M10 8l-4 4 4 4M6 12h11" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function toInitials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

const avatarStyle = {
  width: "30px",
  height: "30px",
  borderRadius: "50%",
  flex: "none",
  background: `linear-gradient(180deg, #3D57E6, ${tokens.color.actionPrimary})`,
  color: "#FFFFFF",
  fontWeight: tokens.typography.weight.bold,
  fontSize: "11px",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
} as const;
