import { useEffect, useState } from "react";

import { tokens } from "../../theme/tokens";

/**
 * True when the viewport is narrow enough that the persistent sidebar should
 * become an off-canvas drawer. Uses `matchMedia` where available (real
 * browsers) and degrades gracefully where it is not (SSR / older jsdom):
 * it falls back to `innerWidth`, and defaults to desktop so tests that do not
 * simulate a viewport exercise the persistent-sidebar layout.
 *
 * A breakpoint hook is unavoidable here: inline styles cannot express a media
 * query, and the drawer-vs-sidebar switch is a genuine structural change, not a
 * cosmetic one.
 */
export function useIsMobile(breakpoint: number = tokens.shellBreakpoint): boolean {
  const query = `(max-width: ${breakpoint - 0.02}px)`;

  const [isMobile, setIsMobile] = useState<boolean>(() => evaluate(query, breakpoint));

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") {
      return;
    }
    const mql = window.matchMedia(query);
    const handler = () => setIsMobile(mql.matches);
    handler();
    mql.addEventListener("change", handler);
    return () => mql.removeEventListener("change", handler);
  }, [query]);

  return isMobile;
}

function evaluate(query: string, breakpoint: number): boolean {
  if (typeof window === "undefined") return false;
  if (typeof window.matchMedia === "function") {
    return window.matchMedia(query).matches;
  }
  return typeof window.innerWidth === "number" ? window.innerWidth < breakpoint : false;
}
