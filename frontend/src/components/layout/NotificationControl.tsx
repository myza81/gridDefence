import { useRef, useState } from "react";

import { tokens } from "../../theme/tokens";
import { useDismiss } from "./useDismiss";

/**
 * Header notification control. Future notifications will surface validation
 * findings, approval requests, completed imports, engineering reviews and audit
 * events (Application Shell Architecture §7 — awareness reflects, it never
 * decides pass/fail).
 *
 * PHASE D PLACEHOLDER: there is NO notification backend, so there is
 * deliberately NO unread badge and NO fabricated count — showing "3" here would
 * misrepresent engineering state. The control opens a clearly-labelled empty
 * state instead of pretending findings exist.
 */
export function NotificationControl() {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  useDismiss(open, containerRef, () => setOpen(false));

  return (
    <div ref={containerRef} style={{ position: "relative" }}>
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="Notifications — none yet"
        title="Notifications"
        onClick={() => setOpen((value) => !value)}
        style={iconButtonStyle}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
          <path d="M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" strokeLinecap="round" />
          <path d="M13.7 21a2 2 0 0 1-3.4 0" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          style={{
            position: "absolute",
            top: "calc(100% + 8px)",
            right: 0,
            width: "300px",
            maxWidth: "calc(100vw - 24px)",
            background: tokens.color.surfacePanel,
            border: `1px solid ${tokens.color.borderDefault}`,
            borderRadius: tokens.radius.md,
            boxShadow: tokens.shadow.panel,
            padding: tokens.space[5],
            zIndex: 60,
            fontFamily: tokens.typography.fontFamily,
          }}
        >
          <p style={{ margin: 0, fontWeight: tokens.typography.weight.semibold, color: tokens.color.textPrimary, fontSize: tokens.typography.size.label }}>
            No notifications
          </p>
          <p style={{ margin: `${tokens.space[2]} 0 0`, color: tokens.color.textSecondary, fontSize: tokens.typography.size.small, lineHeight: tokens.typography.lineHeight.normal }}>
            Validation findings, approval requests and import updates will appear here once these
            engineering services are available. Nothing is being tracked yet.
          </p>
        </div>
      )}
    </div>
  );
}

const iconButtonStyle = {
  width: "34px",
  height: "34px",
  borderRadius: tokens.radius.sm,
  border: "1px solid transparent",
  background: "transparent",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  color: tokens.color.textPrimary,
  cursor: "pointer",
} as const;
