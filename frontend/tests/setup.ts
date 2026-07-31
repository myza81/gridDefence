import "@testing-library/jest-dom/vitest";
import { afterEach, vi } from "vitest";

/**
 * jsdom has no `matchMedia`. The application shell's responsive behaviour
 * (persistent sidebar vs mobile drawer) depends on it, so provide a small
 * polyfill that evaluates `(max-width: Npx)` queries against `window.innerWidth`
 * and re-notifies listeners on `resize`. Tests drive the layout by setting
 * `window.innerWidth` and dispatching a `resize` event.
 */
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList => {
    const listeners = new Set<(event: MediaQueryListEvent) => void>();
    const evaluate = () => {
      const match = /max-width:\s*([\d.]+)px/.exec(query);
      return match ? window.innerWidth <= parseFloat(match[1]) : false;
    };
    const mql = {
      media: query,
      get matches() {
        return evaluate();
      },
      onchange: null,
      addEventListener: (_type: string, cb: (event: MediaQueryListEvent) => void) => listeners.add(cb),
      removeEventListener: (_type: string, cb: (event: MediaQueryListEvent) => void) => listeners.delete(cb),
      addListener: (cb: (event: MediaQueryListEvent) => void) => listeners.add(cb),
      removeListener: (cb: (event: MediaQueryListEvent) => void) => listeners.delete(cb),
      dispatchEvent: () => true,
    } as unknown as MediaQueryList;

    window.addEventListener("resize", () => {
      listeners.forEach((cb) => cb({ matches: evaluate(), media: query } as MediaQueryListEvent));
    });
    return mql;
  };
}

// Keep tests isolated: clear seeded auth tokens and any stubbed globals (e.g.
// stubFetch) between tests so no state leaks across files.
afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.sessionStorage.clear();
  // Reset viewport so a mobile-layout test does not leak into later tests.
  window.innerWidth = 1024;
});
