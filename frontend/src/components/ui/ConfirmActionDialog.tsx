import { useEffect, useRef } from "react";
import type { ReactNode } from "react";

import { tokens } from "../../theme/tokens";
import { Button } from "./Button";

interface ConfirmActionDialogProps {
  open: boolean;
  title: string;
  /** Plain-language statement of the engineering effect (never "Are you sure?"). */
  description: ReactNode;
  /** Extra controls (e.g. a target-status select) rendered above the actions. */
  children?: ReactNode;
  confirmLabel: string;
  /** `danger` for consequential/irreversible effects. */
  confirmTone?: "primary" | "danger";
  /** Backend/validation message to show inside the dialog. */
  error?: string | null;
  pending?: boolean;
  /** Disable confirm (e.g. required reason still empty). */
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Accessible confirmation for a consequential engineering action (Lifecycle
 * actions §12): states the effect explicitly, requires a deliberate confirm,
 * disables repeat submission while pending, and surfaces backend conflicts in
 * place. Modal dialog — focus trapped, Escape / overlay / Cancel dismiss,
 * background scroll locked, focus restored to the trigger.
 */
export function ConfirmActionDialog({
  open,
  title,
  description,
  children,
  confirmLabel,
  confirmTone = "primary",
  error,
  pending = false,
  confirmDisabled = false,
  onConfirm,
  onCancel,
}: ConfirmActionDialogProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);
  // Keep the latest onCancel without making the mount effect depend on it —
  // otherwise the effect re-runs every render and steals focus back to the
  // first control mid-typing.
  const onCancelRef = useRef(onCancel);
  onCancelRef.current = onCancel;

  useEffect(() => {
    if (!open) return;
    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    getFocusable(panelRef.current)[0]?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onCancelRef.current();
        return;
      }
      if (event.key === "Tab") trapTab(event, panelRef.current);
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused.current?.focus?.();
    };
  }, [open]);

  if (!open) return null;

  const titleId = "confirm-dialog-title";
  const descId = "confirm-dialog-description";

  return (
    <div style={{ position: "fixed", inset: 0, zIndex: 90 }}>
      <div aria-hidden="true" onClick={onCancel} style={{ position: "absolute", inset: 0, background: "rgba(15,30,61,0.42)" }} />
      <div
        style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", padding: tokens.space[4] }}
      >
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={descId}
          style={{
            width: "min(440px, 100%)",
            maxHeight: "calc(100dvh - 32px)",
            overflowY: "auto",
            background: tokens.color.surfacePanel,
            borderRadius: tokens.radius.lg,
            boxShadow: tokens.shadow.drawer,
            padding: tokens.space[6],
            fontFamily: tokens.typography.fontFamily,
            display: "flex",
            flexDirection: "column",
            gap: tokens.space[4],
          }}
        >
          <h2 id={titleId} style={{ margin: 0, fontSize: "17px", fontWeight: tokens.typography.weight.bold, color: tokens.color.textPrimary }}>
            {title}
          </h2>
          <div id={descId} style={{ fontSize: tokens.typography.size.label, color: tokens.color.textSecondary, lineHeight: tokens.typography.lineHeight.normal }}>
            {description}
          </div>
          {children}
          {error != null && error !== "" && (
            <p role="alert" style={{ margin: 0, fontSize: tokens.typography.size.small, color: tokens.color.feedbackError }}>
              {error}
            </p>
          )}
          <div style={{ display: "flex", justifyContent: "flex-end", gap: tokens.space[2], marginTop: tokens.space[1] }}>
            <Button variant="secondary" onClick={onCancel} disabled={pending}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={onConfirm}
              loading={pending}
              disabled={confirmDisabled}
              style={confirmTone === "danger" ? { backgroundColor: "#C2410C", borderColor: "#C2410C" } : undefined}
            >
              {confirmLabel}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
}

function trapTab(event: KeyboardEvent, root: HTMLElement | null) {
  const focusables = getFocusable(root);
  if (focusables.length === 0) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  const active = document.activeElement as HTMLElement | null;
  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}
