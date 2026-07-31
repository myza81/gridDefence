import { useEffect } from "react";
import type { RefObject } from "react";

/**
 * Closes a transient surface (menu / popover) on Escape or on a pointer press
 * outside `ref`. Shared by the header's user menu and notification popover so
 * both dismiss consistently and accessibly (Accessibility §14).
 */
export function useDismiss(
  open: boolean,
  ref: RefObject<HTMLElement>,
  onClose: () => void,
): void {
  useEffect(() => {
    if (!open) return;

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    const onPointerDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) onClose();
    };

    document.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, [open, ref, onClose]);
}
