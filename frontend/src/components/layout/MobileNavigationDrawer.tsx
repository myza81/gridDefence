import { useEffect, useRef } from "react";

import { tokens } from "../../theme/tokens";
import { AppSidebar } from "./AppSidebar";
import { BrandMark } from "./BrandMark";

interface MobileNavigationDrawerProps {
  open: boolean;
  onClose: () => void;
}

/**
 * Off-canvas navigation for small screens (Responsive §10). Behaviour:
 *  - opens from the header menu button, closes on Escape, on overlay press,
 *    and after any destination is followed (AppSidebar onNavigate);
 *  - locks background scroll and blocks background interaction while open;
 *  - traps Tab focus within the panel and restores focus to the trigger on
 *    close (Accessibility §14 — accessible dialog behaviour).
 */
export function MobileNavigationDrawer({ open, onClose }: MobileNavigationDrawerProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocused = useRef<HTMLElement | null>(null);

  // Scroll lock + focus capture/restore for the lifetime of the open drawer.
  useEffect(() => {
    if (!open) return;

    previouslyFocused.current = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Move focus into the drawer.
    const focusables = getFocusable(panelRef.current);
    (focusables[0] ?? panelRef.current)?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
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
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 80 }}
      // Prevent background interaction: the overlay covers the viewport.
    >
      <div
        aria-hidden="true"
        onClick={onClose}
        style={{ position: "absolute", inset: 0, background: "rgba(15,30,61,0.42)" }}
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Navigation"
        tabIndex={-1}
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          bottom: 0,
          width: "min(300px, 84vw)",
          background: tokens.color.surfacePanel,
          boxShadow: tokens.shadow.drawer,
          display: "flex",
          flexDirection: "column",
          outline: "none",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            height: tokens.layout.headerHeight,
            padding: "0 12px 0 16px",
            borderBottom: `1px solid ${tokens.color.borderDefault}`,
            flex: "none",
          }}
        >
          <BrandMark />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            style={{
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
            }}
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
            </svg>
          </button>
        </div>
        <div style={{ flex: 1, minHeight: 0 }}>
          <AppSidebar collapsed={false} onNavigate={onClose} />
        </div>
      </div>
    </div>
  );
}

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getFocusable(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  );
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
