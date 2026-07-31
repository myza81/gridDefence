# GridDefence Application Shell V2 — Implementation

Status: Implemented (Phase D). Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15, A12, F4).

This is the **implementation counterpart** to the role-based [Application Shell Architecture](application-shell-architecture.md) and [Navigation Architecture](navigation-architecture.md). Those documents prescribe roles and responsibilities and no layout; this one records the concrete frontend structure that realises them, so contributors can extend the shell without re-deriving it. Where this document and the architecture documents ever diverge, the architecture documents win (Standards Precedence F1).

The shell is the permanent authenticated frame for every GridDefence page. `/login` is deliberately **outside** it (a full-bleed viewport-fit page); every other route renders inside it.

---

## 1. Component structure

All under [`frontend/src/components/layout/`](../../frontend/src/components/layout/), small and single-purpose (no monolith — Component Structure §16):

| Component | Role | Notes |
|---|---|---|
| `AppShell.tsx` | orchestrator | Owns the state spanning roles: rail `collapsed`, mobile `drawerOpen`, viewport class. CSS-grid frame. |
| `AppHeader.tsx` | global-frame | Brand, search placeholder, notifications, user menu, sidebar/drawer toggle. |
| `AppSidebar.tsx` | navigation | Renders the shared taxonomy; used by both the desktop rail and the mobile drawer. |
| `SidebarSection.tsx` / `SidebarItem.tsx` | navigation | Group label + items; `SidebarLeaf` (routed / coming-soon) and `SidebarGroup` (expandable). |
| `Breadcrumbs.tsx` | active-context / orientation | Derived, never hand-authored. |
| `MobileNavigationDrawer.tsx` | navigation (mobile) | Off-canvas dialog: focus trap, scroll lock, Escape / overlay / navigate close. |
| `GlobalSearchPlaceholder.tsx` | global discovery | Inert, accessible, clearly "coming soon". |
| `NotificationControl.tsx` | global awareness | No badge/count; opens an honest empty state. |
| `UserMenu.tsx` | identity | Reflects the IAM user; Sign out. |
| `BrandMark.tsx`, `NavIcon.tsx` | shared presentation | Identity mark; decorative icon registry. |
| `useIsMobile.ts`, `useDismiss.ts` | hooks | Responsive breakpoint; Escape/outside-press dismissal. |

Shared config lives in [`frontend/src/app/`](../../frontend/src/app/): `navigation.ts` (taxonomy + active-route helpers), `breadcrumbs.ts` (resolver), `routes.tsx` (route table + `authenticatedRoutePaths`), `router.tsx` (the protected layout route).

Styling uses the existing typed tokens ([`theme/tokens.ts`](../../frontend/src/theme/tokens.ts)) and the repository's inline-style architecture — no new palette, no CSS framework. A few neutral shell tokens were added within the same cool-blue family (`color.canvas`, `color.textFaint`, `layout.headerHeight/sidebarWidth/sidebarCollapsedWidth`, `shadow.hairline/drawer`, `shellBreakpoint`).

## 2. Layout

```text
┌───────────────────────────────────────────────┐  grid rows: 56px / 1fr
│ Header (global-frame, spans full width)        │  grid cols: sidebar / 1fr
├───────────────┬───────────────────────────────┤
│ Sidebar       │ Breadcrumbs (fixed)            │
│ (persistent,  ├───────────────────────────────┤
│  own scroll)  │ <main> — workspace host        │
│               │ (the only scrolling region)    │
└───────────────┴───────────────────────────────┘
```

The outer frame is `height: 100dvh; overflow: hidden`; only `<main>` scrolls, so the header, sidebar, and breadcrumb row never move and the document never overflows horizontally.

## 3. Navigation taxonomy (engineering domains, not modules)

Defined once in `app/navigation.ts` and consumed by the sidebar, the drawer, and breadcrumbs. Organised by how engineers think, not by backend packages (Navigation Architecture §5):

```text
Home                                   → /

ENGINEERING DOMAINS
  Registries
    Substations                        → /substations
    Circuits                           → /circuits
    Transformers                       → /transformers
    ALSF Registry                      → /automatic-load-shedding-functionality
    Sensitive Customers                → /sensitive-customer-registry
  Network & PSS/E
    Network Explorer                   → /network-model
    Network Substations                → /network-model/substations
    Network Traversal                  → /network-model/traversal
    Snapshot Verification              → /network-model/verification
    PSS/E Import                       → /psse-integration/import
    PSS/E History                      → /psse-integration/history
    PSS/E Status                       → /psse-integration/current-status
  Defence Schemes
    UFLS Schemes                       → /ufls/schemes
    Stage Setting Sets                 → /stage-setting-sets
    UVLS                               → coming-soon (no route)
    EMLS                               → coming-soon (no route)
  Continuous Evaluation                → coming-soon (no route)

SYSTEM
  Reports                              → coming-soon (no route)
  Administration
    Users                              → /users
    Roles                              → /roles
    Permissions                        → /permissions
```

**Coming-soon entries carry no route** and render as visibly unavailable (a muted "Soon" tag), never as a dead link — enforced by the navigation-integrity test.

## 4. Route inventory — what appears in navigation and what does not

The sidebar links only to **stable module entry points**. Detail, create, action, and internal diagnostic routes are intentionally *not* navigation entries (Route inventory §13); they are reached from within their module and are still fully routed and reachable. Excluded from the sidebar (non-exhaustive): `/*/new`, `/*/:id` detail pages, `/psse-integration/import/inspect`, `/psse-integration/batches/:id`, `/psse-integration/topology-versions/:id/equipment-map`, `/network-model/substations/:id/bays`, `/network-model/substations/:id/connectivity`, `/network-model/boundary-pocket-evaluator` (diagnostic tool), `/ufls/versions/:id`, `/ufls/versions/:id/publication-review`, and the sensitive-customer reference-data admin routes.

Breadcrumbs still orient the engineer on those routes (e.g. `/substations/new` → Home / Registries / Substations / New; a dynamic record → … / Substations / Details). Dynamic record names are **not** fetched to label a crumb (that would be an extra API call and a second source of truth); a generic terminal label is used until route-specific metadata exists.

## 5. Responsive behaviour

- **Desktop (≥ 900px):** persistent sidebar, optionally collapsible to an icon rail (header toggle; local component state, not persisted — Sidebar Interaction §4). The active item shows a wash + accent bar and `aria-current="page"`; its parent group is highlighted and auto-expanded.
- **Tablet:** same persistent sidebar; can be collapsed to the rail for more width.
- **Mobile (< 900px):** the sidebar becomes an off-canvas drawer opened from the header menu button. The drawer traps focus, locks background scroll, blocks background interaction, closes on Escape / overlay press / after navigation, and restores focus to the trigger.

The breakpoint lives in `tokens.shellBreakpoint` and is read via `useIsMobile` (`matchMedia`, with an `innerWidth` fallback). Layout uses no CSS media queries (inline-style architecture); the drawer-vs-sidebar switch is the one genuine structural breakpoint.

## 6. Placeholders — honesty over visual completeness

Two elements from the approved mockup are **deliberately omitted** in this phase because they would misrepresent engineering state that does not yet exist (Application Shell Architecture §3/§7, Navigation Architecture §16):

- **Engineering-scope band** (selected snapshot / scheme / registry version) — no such selection state exists; showing pills would imply one. The breadcrumb row honestly fills that band.
- **Ambient-status bar** (live unread counts, import %, topology version) — no backend feeds it.

Correspondingly:
- **Global search** is an inert, focusable, clearly-labelled "coming soon" control — no query, no API, no fabricated results.
- **Notifications** show no badge/count and open an explicit empty state — no fabricated findings.
- **User menu** shows the real IAM identity and Sign out only; Profile/Preferences are omitted (no such routes), and no role name is shown (AuthContext exposes a permission set, not a display role).

When real scope/awareness state lands, these become live surfaces without structural change.

## 7. Authentication integration

`/login` (outside the shell) → on success redirects to `/`. The authenticated layout route (`router.tsx`) gates **first** (`ProtectedRoute`) and only then renders `AppShell` around `<Outlet/>`, so an anonymous visitor is redirected without any shell chrome flashing, and protected content never renders transiently. Logout uses the existing `AuthContext.logout()`.

## 8. Authenticated visual testing

Two reproducible mechanisms replace Phase C's temporary unguarded-route workaround; **production routing is never modified for screenshots**:

- **Component tests:** [`tests/authFixture.tsx`](../../frontend/tests/authFixture.tsx) `renderAuthenticated()` seeds a session token and mocks only the IAM calls `AuthProvider` makes (`GET /users/me`, `GET /users/:id/roles`) plus `POST /auth/logout`. Test-only; never shipped.
- **Browser screenshots:** [`frontend/dev/shellPreview.tsx`](../../frontend/dev/shellPreview.tsx) + `shell-preview.html` mount the real shell with the same stubbed session. Not referenced by `index.html`, so `vite build` never bundles it. Run `npm run dev`, open `http://localhost:5173/shell-preview.html` (optionally `?route=/substations`). The harness writes layout metrics to `document.title` for headless overflow checks.

## 9. Adding a module to the shell

1. Register the route in [`app/routes.tsx`](../../frontend/src/app/routes.tsx).
2. Add a navigation entry (with `route` and an `icon`) to the right domain group in [`app/navigation.ts`](../../frontend/src/app/navigation.ts) — or, if the workspace does not exist yet, add it as `availability: "coming-soon"` with no route.
3. Nothing else. Breadcrumbs, active-state, the mobile drawer, and the route-integrity test all update automatically from those two edits. If a new icon is needed, add it to `NavIcon.tsx`.

## 10. Accessibility

Semantic landmarks (`<header>`, `<nav aria-label="Primary">`, `<nav aria-label="Breadcrumb">`, `<main>`), `aria-current="page"` on the active item, `aria-expanded` on groups, accessible names on every icon-only control, icons never used alone in the expanded shell, an accessible dialog drawer (focus trap + restore), and dismissable menus (Escape + outside press). Colour contrast follows the existing token palette.
