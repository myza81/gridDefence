/**
 * Shared GridDefence navigation taxonomy — the single source of truth for the
 * application shell's navigation.
 *
 * WHY ONE CONFIG: the desktop sidebar, the mobile drawer, the breadcrumb
 * resolver (see ./breadcrumbs.ts), and the navigation-integrity test all read
 * from this one structure, so labels and routes cannot drift between them
 * (Navigation Architecture §17 — domains contribute destinations into one
 * shared model; the shell composes them, it is not edited per capability).
 *
 * ORGANISED BY ENGINEERING DOMAIN, NOT SOFTWARE MODULE (Navigation
 * Architecture §1, §5): an engineer should reach work by meaning, never by
 * knowing the backend's package layout. One domain here may be served by
 * several implementation modules (e.g. "Network & PSS/E" spans the
 * network-model and psse-integration modules).
 *
 * HONESTY (Navigation Architecture §2.8, §16): every `route` below points at a
 * real, registered route in ../app/router.tsx. Planned-but-unbuilt domains are
 * marked `availability: "coming-soon"` and carry NO route, so the shell renders
 * them as visibly unavailable rather than as a dead link to an unrelated place.
 * The navigation-integrity test enforces both halves of this contract.
 *
 * This is presentation configuration only — no engineering logic, no access
 * decision (that stays with IAM and the owning domains; CLAUDE.md A12, F4).
 */

export type NavIconName =
  | "home"
  | "registries"
  | "substation"
  | "circuit"
  | "transformer"
  | "relay"
  | "sensitive"
  | "network"
  | "traversal"
  | "verification"
  | "import"
  | "history"
  | "status"
  | "schemes"
  | "stage"
  | "uvls"
  | "emls"
  | "evaluation"
  | "reports"
  | "administration"
  | "users"
  | "roles"
  | "permissions";

export type NavAvailability = "available" | "coming-soon";

export interface NavItem {
  /** Stable id — also used as a React key and test handle. */
  id: string;
  label: string;
  /** Destination path. Omitted for pure group parents and coming-soon items. */
  route?: string;
  icon?: NavIconName;
  children?: NavItem[];
  /** Defaults to "available" when omitted. */
  availability?: NavAvailability;
}

export interface NavSection {
  id: string;
  /** Uppercase group heading; omitted for the leading Home row. */
  label?: string;
  items: NavItem[];
}

/**
 * The permanent navigation taxonomy. Adding a module means adding an entry here
 * (and a matching route in router.tsx) — nowhere else in the shell.
 */
export const NAVIGATION: NavSection[] = [
  {
    id: "primary",
    items: [{ id: "home", label: "Home", route: "/", icon: "home" }],
  },
  {
    id: "engineering-domains",
    label: "Engineering Domains",
    items: [
      {
        id: "registries",
        label: "Registries",
        icon: "registries",
        children: [
          { id: "substations", label: "Substations", route: "/substations", icon: "substation" },
          { id: "circuits", label: "Circuits", route: "/circuits", icon: "circuit" },
          { id: "transformers", label: "Transformers", route: "/transformers", icon: "transformer" },
          {
            id: "alsf",
            label: "ALSF Registry",
            route: "/automatic-load-shedding-functionality",
            icon: "relay",
          },
          {
            id: "sensitive-customers",
            label: "Sensitive Customers",
            route: "/sensitive-customer-registry",
            icon: "sensitive",
          },
        ],
      },
      {
        id: "network",
        label: "Network & PSS/E",
        icon: "network",
        children: [
          { id: "network-explorer", label: "Network Explorer", route: "/network-model", icon: "network" },
          {
            id: "network-substations",
            label: "Network Substations",
            route: "/network-model/substations",
            icon: "substation",
          },
          {
            id: "network-traversal",
            label: "Network Traversal",
            route: "/network-model/traversal",
            icon: "traversal",
          },
          {
            id: "snapshot-verification",
            label: "Snapshot Verification",
            route: "/network-model/verification",
            icon: "verification",
          },
          { id: "psse-import", label: "PSS/E Import", route: "/psse-integration/import", icon: "import" },
          { id: "psse-history", label: "PSS/E History", route: "/psse-integration/history", icon: "history" },
          {
            id: "psse-status",
            label: "PSS/E Status",
            route: "/psse-integration/current-status",
            icon: "status",
          },
        ],
      },
      {
        id: "defence-schemes",
        label: "Defence Schemes",
        icon: "schemes",
        children: [
          { id: "ufls", label: "UFLS Schemes", route: "/ufls/schemes", icon: "schemes" },
          { id: "stage-setting-sets", label: "Stage Setting Sets", route: "/stage-setting-sets", icon: "stage" },
          { id: "uvls", label: "UVLS", icon: "uvls", availability: "coming-soon" },
          { id: "emls", label: "EMLS", icon: "emls", availability: "coming-soon" },
        ],
      },
      {
        // A real planned domain (continuous-evaluation-architecture.md) with no
        // engineer-facing workspace yet — surfaced honestly as coming-soon.
        id: "continuous-evaluation",
        label: "Continuous Evaluation",
        icon: "evaluation",
        availability: "coming-soon",
      },
    ],
  },
  {
    id: "system",
    label: "System",
    items: [
      { id: "reports", label: "Reports", icon: "reports", availability: "coming-soon" },
      {
        id: "administration",
        label: "Administration",
        icon: "administration",
        children: [
          { id: "users", label: "Users", route: "/users", icon: "users" },
          { id: "roles", label: "Roles", route: "/roles", icon: "roles" },
          { id: "permissions", label: "Permissions", route: "/permissions", icon: "permissions" },
        ],
      },
    ],
  },
];

/** Every navigation item flattened depth-first (parents before children). */
export function flattenNavItems(sections: NavSection[] = NAVIGATION): NavItem[] {
  const out: NavItem[] = [];
  const walk = (items: NavItem[]) => {
    for (const item of items) {
      out.push(item);
      if (item.children) walk(item.children);
    }
  };
  for (const section of sections) walk(section.items);
  return out;
}

/** Every routed navigation item (has a destination). */
export function routedNavItems(sections: NavSection[] = NAVIGATION): (NavItem & { route: string })[] {
  return flattenNavItems(sections).filter(
    (item): item is NavItem & { route: string } => typeof item.route === "string",
  );
}

/**
 * Whether `itemRoute` should be shown as the active location for `pathname`.
 * The Home route matches only exactly (otherwise it would light up everywhere);
 * every other route matches its own path and any deeper detail/child path
 * (e.g. `/substations` is active on `/substations/123`), so a parent group and
 * its entry stay highlighted while the engineer works inside a record.
 */
export function isRouteActive(itemRoute: string, pathname: string): boolean {
  if (itemRoute === "/") return pathname === "/";
  return pathname === itemRoute || pathname.startsWith(`${itemRoute}/`);
}

/** True when any descendant of `item` is the active route (for parent groups). */
export function isGroupActive(item: NavItem, pathname: string): boolean {
  if (item.route && isRouteActive(item.route, pathname)) return true;
  return (item.children ?? []).some((child) => isGroupActive(child, pathname));
}
