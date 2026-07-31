/**
 * Breadcrumb resolution for the application shell.
 *
 * Breadcrumbs are DERIVED from the shared navigation taxonomy (./navigation.ts)
 * plus the current pathname — they are never hand-authored on individual pages
 * (Navigation Architecture §9: orientation must always be available; the shell
 * provides it once). This keeps the trail consistent with the sidebar and
 * impossible to drift.
 *
 * The last crumb is the current location and is NOT a link (it carries
 * aria-current in the view). Ancestor crumbs link to their own routes where one
 * exists; a pure grouping ancestor (e.g. "Registries") has no route and renders
 * as plain text.
 *
 * Dynamic record routes (`/substations/:id`, `/ufls/versions/:id`, …) have no
 * dedicated navigation entry. Per the Phase D brief we do NOT fetch the record's
 * name to label them (that would be an extra API call and a second source of
 * truth); we show a generic terminal label until route-specific metadata
 * exists. Honest and stable beats a fabricated object name.
 */
import type { NavItem } from "./navigation";
import { NAVIGATION } from "./navigation";

export interface Breadcrumb {
  label: string;
  /** Present ⇒ render as a link. Absent ⇒ current page / non-navigable group. */
  to?: string;
}

/** Known trailing path segments → human labels for detail/action routes. */
const TRAILING_SEGMENT_LABELS: Record<string, string> = {
  new: "New",
  candidates: "Candidates",
  inspect: "Inspect",
  bays: "Bays",
  connectivity: "Connectivity",
  "equipment-map": "Equipment Map",
  "publication-review": "Publication Review",
  "boundary-pocket-evaluator": "Boundary Pocket Evaluator",
  "facility-sectors": "Facility Sectors",
  "sensitivity-classifications": "Sensitivity Classifications",
};

/** Fallback domain label for orphan routes with no navigation prefix match. */
const ORPHAN_ROOT_LABELS: Record<string, string> = {
  "psse-integration": "PSS/E",
  ufls: "Defence Schemes",
  "network-model": "Network & PSS/E",
};

const HOME: Breadcrumb = { label: "Home", to: "/" };

/** Depth-first chain (ancestors first) to the routed item best matching `pathname`. */
function findRoutedChain(pathname: string): NavItem[] | null {
  let best: NavItem[] | null = null;
  let bestLen = -1;

  const walk = (items: NavItem[], ancestors: NavItem[]) => {
    for (const item of items) {
      const chain = [...ancestors, item];
      if (item.route && isPrefix(item.route, pathname) && item.route.length > bestLen) {
        best = chain;
        bestLen = item.route.length;
      }
      if (item.children) walk(item.children, chain);
    }
  };

  for (const section of NAVIGATION) walk(section.items, []);
  return best;
}

/** True when `route` equals `pathname` or is a parent segment of it. */
function isPrefix(route: string, pathname: string): boolean {
  if (route === "/") return pathname === "/";
  return pathname === route || pathname.startsWith(`${route}/`);
}

function humanizeSegment(segment: string): string {
  return (
    TRAILING_SEGMENT_LABELS[segment] ??
    // Numeric / uuid-like id → a stable generic label (no record fetch, by design).
    (/^[0-9a-f-]{6,}$/i.test(segment) || /^\d+$/.test(segment) ? "Details" : titleCase(segment))
  );
}

function titleCase(segment: string): string {
  return segment
    .split("-")
    .map((word) => (word.length > 0 ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}

/**
 * Build the breadcrumb trail for a pathname. Always starts at Home; the final
 * entry is the current location (no `to`).
 */
export function resolveBreadcrumbs(pathname: string): Breadcrumb[] {
  if (pathname === "/") {
    return [{ label: "Home" }];
  }

  const chain = findRoutedChain(pathname);

  if (!chain) {
    // Orphan route (e.g. /ufls/versions/:id) — no navigation entry is a prefix.
    const firstSegment = pathname.split("/").filter(Boolean)[0] ?? "";
    const rootLabel = ORPHAN_ROOT_LABELS[firstSegment] ?? titleCase(firstSegment);
    return [HOME, { label: rootLabel }];
  }

  const crumbs: Breadcrumb[] = [HOME];
  const matched = chain[chain.length - 1];
  const ancestors = chain.slice(0, -1);

  for (const ancestor of ancestors) {
    crumbs.push(ancestor.route ? { label: ancestor.label, to: ancestor.route } : { label: ancestor.label });
  }

  const matchedRoute = matched.route as string;
  if (pathname === matchedRoute) {
    crumbs.push({ label: matched.label }); // current
    return crumbs;
  }

  // On a deeper detail/action route: the matched entry becomes a link and a
  // generic terminal crumb names the sub-route.
  crumbs.push({ label: matched.label, to: matchedRoute });
  const remainder = pathname.slice(matchedRoute.length).split("/").filter(Boolean);
  const terminal = remainder[remainder.length - 1] ?? "";
  crumbs.push({ label: humanizeSegment(terminal) });
  return crumbs;
}
