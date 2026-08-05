# Substation Registry — Frontend (Registry Workspace)

Status: Implemented (Phase E). Companion to [substation-registry.md](substation-registry.md) (authoritative domain/DB/API spec) and the [Application Shell V2 implementation](application-shell-implementation.md). Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15, A6, A12).

This records how the Substation Registry is **presented**. The backend contract, lifecycle rules (ADR-014), mnemonic/alias rules, and reference-data ownership are unchanged and remain the sole authority; the frontend reflects them and never re-decides them.

## Routes

| Route | Page | Navigation |
|---|---|---|
| `/substations` | `SubstationListPage` | Sidebar entry (Registries → Substations) |
| `/substations/new` | `SubstationCreatePage` | Not a nav entry (reached from the list action) |
| `/substations/:substationId` | `SubstationDetailPage` | Not a nav entry (reached by opening a record) |

Edit is **inline** on the detail workspace (an "Edit" section), not a separate route — reconciled with the actual inventory; no `/edit` alias was added. Breadcrumbs resolve via the Phase D navigation config; dynamic record segments get a generic terminal label with **no** extra record-name fetch.

## Landing page (`/substations`)

`PageHeader` (title "Substation Registry", one-line engineering description, live result count, permission-gated "Register substation" action) → a filter `Card` → the registry table (desktop) or record cards (mobile) → pagination.

**Columns (decision-relevant, not every field):** Mnemonic · Substation (name) · Switchyards (voltage yards, composed client-side per ADR-009/A2-F2) · Region · GM Zone · Grid Owner · Lifecycle status (`Badge`) · Open. Row → `/substations/:id` via a labelled "Open" link (not an icon-only control; whole-row click avoided for accessibility).

## Search, filters, sorting

Server-driven (the list is paginated server-side): `search` (mnemonic/name, debounced 300 ms), `region_id`, `gm_zone_id`, `operational_status_id`. Discrete filters + page are persisted in the URL via `useSearchParams` (shareable/deep-linkable — no new routing framework); search mirrors into the URL after debounce. "Reset filters" clears all. The status filter offers only the four ADR-014 substation states. **Sorting is intentionally not offered** — the backend list has no sort parameter, and a client-only sort would sort a single page, misrepresenting the dataset (documented gap).

## Lifecycle presentation

Status is `operational_status_id` (reference data), not a separate enum. [`lifecycle.ts`](../../frontend/src/modules/substation_registry/lifecycle.ts) is a typed **mirror** of the backend `_STATUS_TRANSITIONS`/ADR-014 (badge tone per code; the legal target states from a given state; the valid initial states). It introduces no new state or rule — if ADR-014 changes, this table and the service allow-list change together. `Badge` carries meaning in the **text label**; tone + dot only reinforce it (never colour alone). Terminal (Decommissioned / Entered in Error) and non-substation legacy codes offer no transitions.

## Create flow

Shared grouped `SubstationForm` (Identity → Classification → Location & metadata → Remarks) with accessible reference-data selectors, the mnemonic identity rule shown inline, client validation of required fields and the latitude/longitude pair, double-submit prevention (button `loading`/`disabled`), values preserved on server rejection, and navigation to the new record on success. State is optional (ADR-026): omitted entirely when "None".

## Detail workspace

Grouped `DetailSection` cards: **Identity**, **Engineering Classification**, **Lifecycle** (current-status badge + an audited "Change status" action), **Audit & Revision** (created/updated who+when), then the **Edit** section (shared `SubstationForm` in edit mode — identity/classification/remarks; status is never a silent edit). The **retained Equipment-Registry sections** (Switchyards add/correct/restore, Transformers, Engineering Connectivity) and the Alias history + Audit log follow. Related-equipment counts are real query results, never fabricated.

**Density (presentation only):** the four summary cards and the Edit form carry **no repetitive descriptive prose** — card/field labels already convey meaning, so the workspace is compact and information-focused. The Edit form drops the redundant "Identity" subsection heading and its descriptions; the **mnemonic identity rule is retained** (condensed) because it states a real backend rule (≤10 chars, unique, not reusable for another substation). Engineering-meaningful section notes on the retained equipment sections (ADR-009 switchyards, connectivity provenance) are kept.

**PSS/E bus number — not shown here (deliberate).** The authoritative substation↔PSS/E-bus correlation is **snapshot-scoped and one-to-many**: `TopologyBus.substation_id`, resolved per `TopologyVersion` and recomputed as data changes (ADR-006, ADR-003; [psse-integration-module.md](psse-integration-module.md)). A physical substation commonly maps to several buses (per voltage level / area) and differs across imported snapshots. The Registry's own `psse_bus_number` column is a legacy optional 1:1 cross-reference (usually null) that would misrepresent that relationship as a permanent single identity — and the detail page has **no honest snapshot context**. So the singular "PSS/E bus number" row is **removed from the Identity card**; no value is inferred, fetched, or collapsed, and no frontend mapping is added. The backend field and its contract are unchanged; ownership was already settled by ADR-006/ADR-003, so **no new ADR** is required.

**Deferred: a "Network Representation" section.** A read-only, snapshot-scoped view of a substation's correlated PSS/E buses (bus number · name · nominal voltage · correlation status · snapshot identity) would belong to the operational/network layer, not registry identity. It is deferred: this page has no selected/current snapshot to cite honestly, and such a view would duplicate the existing PSS/E Integration / Network Model workflow (which owns `TopologyBus.substation_id` correlation with provenance). Revisit if/when the shell carries an explicit snapshot context (Application Shell Architecture §3).

### The reference workspace pattern (Circuit / Transformer / Relay / Sensitive-Customer registries should follow this)

The detail page is the intended UX standard for every GridDefence registry record. Its shape:

- **Inspect first, edit on purpose.** The record reads as compact summary cards; **editing is an accessible disclosure that is collapsed by default**. The engineer is never confronted with a large form just to read a record. The form expands inline (no route change, no modal), Cancel and a successful Save both collapse it, entered values persist while it is open, and validation is unchanged. Focus moves into the edit region on open and returns to the trigger on close; the trigger carries `aria-expanded` / `aria-controls` (WAI-ARIA disclosure). A successful save collapses the form.
- **A page command area, not a scattered link.** A top action bar carries `← Back to Registry` on the left and permission-gated actions on the right: **Edit** (the disclosure trigger) and **Change status** (which *focuses/scrolls to* the Lifecycle card's own audited control — it never duplicates lifecycle logic or opens a second dialog).
- **Engineering identity is visually clear.** The header shows the **official name** (h1) with the **mnemonic** rendered beneath as the authoritative identifier (bold, tabular numerals, tracked) and the lifecycle **badge** below it. The Identity card re-states the mnemonic with the same identifier styling.
- **Lifecycle prominence.** The current status uses the larger (`md`) badge so it is the focal value, stronger than its "Current status" label; the Change-status control sits in the card header, aligned with the status.
- **Compact audit.** Created / Last-updated render as `DD Mon YYYY · HH:MM` with the actor on a second line, avoiding long wrapped timestamp lines — same information, denser.
- **Density.** Summary cards size to their own content (no stretch), with tightened inter-card spacing and no descriptive prose; the two-column desktop layout collapses to one column on narrow viewports; the retained Equipment-Registry sections follow below the disclosure.

Reusable pieces that carry this pattern forward: `PageHeader` (title/description/actions), `DetailSection` + `MetadataList`, `Badge` (`size="md"` for a focal status), `ConfirmActionDialog`, and the shared module `…Form` in an `mode="edit"` disclosure. A future registry composes the same, swapping only its own fields, lifecycle mirror, and equipment sections.

### Composition: 2×2 summary grid + grouped lower workspace

The detail page is composed, not monolithic — the page owns the header, the summary grid, the edit disclosure and the status dialog; each lower section is a self-contained component under [`components/detail/`](../../frontend/src/modules/substation_registry/components/detail/) that owns its own query/mutations. This is the "one coherent workspace" structure:

- **Stable 2×2 summary grid.** The four cards use `grid-template-columns: repeat(2, minmax(0, 1fr))` on desktop (Identity · Engineering Classification / Lifecycle · Audit & Revision) and a single-column stack below `tokens.shellBreakpoint` (via `useIsMobile`). Deterministic — the Audit card never floats alone into a third row.
- **Grouped lower workspace.** A `WorkspaceGroup` heading precedes each group: **Engineering Information** (Switchyards, Transformers, Engineering Connectivity), **Engineering History** (Alias History), **Governance** (Audit Log). Section cards render at heading level 3 under the group's level-2 label.
- **One design language.** Every section shares the same card chrome (`DetailSection`), table styling (`components/detail/styles.ts`), `Badge`, `EmptyState`/`ErrorState`, form controls and `ConfirmActionDialog`. No browser-default `<ul>`/`<input>`/`<select>` remain, and no `window.confirm`.

**Switchyards (modernised, ADR-009/ADR-027).** One structured record card per voltage level: label + lifecycle `Badge`, read-only Commissioned/Latitude/Longitude, and — with `equipment_registry.write` — an intentional per-yard **Edit** disclosure, **Add switchyard** disclosure, and audited **Mark as Entered in Error** / **Restore** via `ConfirmActionDialog` (reason required; never a delete/undelete; Restore always → Active). Entered-in-error yards are hidden by default behind a toggle and shown with a distinct badge.

**Transformers (substation-local view).** A concise table (desktop) / cards (mobile) — short name, HV↔LV windings, capacity, lifecycle badge — with the primary action opening the full Transformer record in its own registry. This is *not* the Transformer Registry embedded whole.

**Engineering Connectivity.** A relationship table (circuit · bay · voltage · line type · lifecycle badge · other connected substations · open) over the manually-maintained Circuit/CircuitTerminal baseline — explicitly **not** PSS/E operational topology.

**Alias History (Engineering History).** A compact historical table: each former mnemonic with its valid period and a Current/Retired badge (identity history is never overwritten).

**Audit Log (Governance).** A read-only governance table (when · actor · field change · reason), verbatim and newest-first per the API — deliberately distinct from the Audit & Revision summary card (which shows only created/updated accountability). No editing controls.

**Query invalidation.** Each section owns its query with stable keys (`["substation", id, "voltage-yards"|"transformers"|"circuits"]`, plus the substation alias/audit hooks). Switchyard mutations invalidate only the switchyard query (which drives the voltage summary); no unrelated modules are invalidated; consequential mutations are not auto-retried.

## Lifecycle action (status change)

`ConfirmActionDialog` — offers only the legal target states for the current status (reflecting rules, not relying on rejection), requires a deliberate confirm, takes an audited reason, uses a danger tone for "Entered in Error", disables repeat submission while pending, and surfaces the backend's own rejection message in place. Cancel makes no request.

## Error / loading / empty states

Backend messages are surfaced verbatim via `ApiError.message` (structured `{code,message}`); business errors are **not field-tagged** by the backend, so create/edit rejections show as a form-level summary (documented gap — no message parsing). `ErrorState` for load failures (with safe retry for reads); distinct `EmptyState` for "No substations registered" vs "No substations match the current filters"; honest not-found on the detail route. No mock data in the production UI.

## Permissions

`substation_registry.write` gates the Register action, the detail Edit section, and the status action; reads are open (reference data). The frontend is never the security boundary — the backend re-checks and a 403 surfaces honestly.

## Query & cache design

Module-owned hooks ([`hooks.ts`](../../frontend/src/modules/substation_registry/hooks.ts)) with hierarchical keys (`substationKeys`): create invalidates the lists; update/status invalidate the record + lists. Pages consume hooks, not `apiClient` directly. `placeholderData` keeps the previous page visible during refetch (no flash).

## Reusable components introduced

`components/ui/`: `PageHeader`, `Badge`, `EmptyState`, `ErrorState`, `SelectField`, `DetailSection`, `MetadataList`, `ConfirmActionDialog`; `hooks/useDebouncedValue`. Bounded and registry-shaped — a pattern the **Equipment Registry** (Circuits/Transformers) can reuse next, not a universal table framework.

## Responsive decision

Desktop/tablet: a full engineering table in a horizontally-scrollable card (scroll confined to the table, never the document). Mobile (< 900 px): a **structured record-card list** (mnemonic, status badge, name, GM Zone · voltage, "Open record") — the desktop table is not squeezed into unreadable columns.

## Authenticated visual testing

Component tests mock the module + reference-data endpoints (existing `tests/testUtils` `stubFetch`). Browser screenshots use the dev-only harness [`dev/shellPreview.tsx`](../../frontend/dev/shellPreview.tsx) (`?route=/substations`, `/substations/new`, `/substations/:id`) — production routing is never changed for screenshots.

## How future registries reuse this

Add the module's routes + a navigation entry (Phase D), then compose the same primitives: `PageHeader` + filter `Card` + server-paginated table/cards + `Badge` for lifecycle + module hooks + `SubstationForm`-style grouped form + `ConfirmActionDialog` for consequential actions. Keep the lifecycle mirror beside the module (one typed source), and surface backend messages verbatim.

## Known limitations / deferred

- Backend business errors are not field-tagged → form-level error summary (no message parsing).
- No optimistic-locking/stale-version contract → no concurrency-conflict UI.
- No server sort parameter → no column sorting.
- Dedicated `/substations/:id/edit` route deferred (edit is inline).
- Equipment-Registry detail sections are retained as-is (out of Phase E scope to redesign).
- Singular `PSS/E bus number` removed from the Identity card (snapshot-scoped, one-to-many correlation belongs to the network/operational layer); a snapshot-scoped "Network Representation" correlation section is deferred until an explicit snapshot context exists.

## Geographic map view (Phase E.1)

A complementary geographic presentation of the *same* authoritative registry records the table shows — **not** a PSS/E topology viewer, a live operational map, a power-flow view, or an electrical-connectivity model. It draws **no lines**: geographic proximity is not electrical connectivity (stated in on-screen copy).

- **Purpose:** let engineers locate and inspect registered substations across Peninsular Malaysia, and see which records lack usable coordinates.
- **Route / view state:** `/substations` stays the single entry point; a `[Table] [Map]` switch toggles `?view=map` in the URL (shared with the existing filter query state). The table is the default; filters are shared, so the two views never drift; view is deep-linkable and back/forward-safe. No new route, no duplicate sidebar entry.
- **Coordinate authority:** the map plots **`Substation.latitude/longitude`** — Substation Registry owns geography (ADR-008; switchyard coordinates are per-yard GIS metadata and are **not** substation geography). No representative-switchyard rule, no centroid, no geocoding, no inference of missing coordinates. Because the DB enforces the geolocation pair + range, a persisted coordinate is present-and-valid or absent, so the projection's `coordinate_status` is `present` | `missing`.
- **API projection:** a new read-only `GET /api/v1/substations/map` (Router→Service→Repository) returns the lightweight features (id, mnemonic, official_name, lifecycle, region/gm_zone/state/grid_owner, lat/long, `coordinate_status`) for **all** records matching the *same* filters as the list (unpaginated — a map needs every coordinate-bearing record), plus `mapped_count` / `missing_coordinate_count`. Reads are open to any authenticated user (reference data). No detail endpoint is fetched per record.
- **Engineering Map Framework:** `components/map/EngineeringMap.tsx` is a **generic, reusable** MapLibre GL wrapper — it owns the map, navigation + reset-to-Peninsular-Malaysia controls, attribution, clustering, and graceful basemap failure, and knows nothing about substations. Callers pass `EngineeringMapLayer`s (GeoJSON points + a category→colour map), so future engineering layers (Transformers, Circuits, Relays, Sensitive Customers, defence-scheme overlays, analytical layers) plug in without changing the framework. The Substation view supplies the only initial layer.
- **Library & tiles:** [MapLibre GL JS](https://maplibre.org/) (BSD-3, open). The basemap is configured through a **style URL** in `VITE_MAP_STYLE_URL` (not a raw tile URL), so a deployment can point at a public dev style now and an internally-hosted production map service later without code changes. **No public provider is hard-coded as a production service:** when the variable is unset or the style fails, the map renders a "basemap unavailable" state while the markers-as-list and details stay fully usable. Attribution is shown (MapLibre `AttributionControl`).
- **Markers & clustering:** one marker per coordinate-bearing substation, coloured by **lifecycle** (only) — with a text legend and an accessible record list, so colour is never the sole indicator. Entered-in-Error is visibly distinct (danger tone + list badge). MapLibre native clustering at broad zoom; the accessible record list is the non-map equivalent (clusters never hide lifecycle misleadingly).
- **Selected-record details:** selecting a marker or list row opens a details panel (Mnemonic, Official name, Lifecycle badge, Region, GM Zone, Grid Owner **code**, State) with **Open substation →** to the existing detail route. No edit/lifecycle workflows in the map (maintenance stays in the detail workspace).
- **Missing coordinates:** counted (`N mapped · M without coordinates`) and **listed** (each flagged `NO COORDS`, still openable) — never silently dropped. Coordinate quality (lat-only / out-of-range / malformed) cannot persist (DB pair + range constraints), so the map only distinguishes present vs missing; it never mutates registry data.
- **Accessibility:** the map is a progressive enhancement — an accessible, keyboard-operable record list is always present, so the map is never the only way to find or open a substation. Zoom/reset controls have accessible names; lifecycle is text; selection is announced via the details panel.
- **States:** map-data loading / retryable error (table stays available) / empty / all-filtered-out / basemap-unavailable — no blank grey rectangle.
- **Deferred:** geographic **line overlays** (a separate, governed capability — never drawn from proximity/mnemonic similarity/shared GM Zone/PSS/E without snapshot context). The **coordinate→State resolution** addendum is deferred to [ADR-030](../adr/ADR-030-coordinate-assisted-state-resolution.md) (proposal delivered; not implemented until approved).

### Cartographic enhancement + offline capability (Phase E.1A)

The map engine and framework are unchanged (still MapLibre GL JS + `EngineeringMap` + read-only projection); the **cartographic experience** and **offline resilience** were enhanced. Full detail lives in [engineering-map.md](engineering-map.md); in summary:

- **Selectable basemap styles** (Standard / Satellite / Terrain) built from a **config object** driven by per-style env vars (`VITE_MAP_STYLE_STANDARD|SATELLITE|TERRAIN`), so future styles (Dark, High-Contrast, Utility) are a one-line addition. Availability comes from configuration — unset styles are omitted, not offered-then-failing. Style switching preserves camera, selection and filters.
- **Offline-first**: two operating modes (connected dev vs offline/internal production) by configuration alone; time-bounded loads (no infinite retry); a deliberate fallback hierarchy (selected → local Standard → neutral local canvas → record list) that **never silently switches to a public provider**; availability detected from real resource load success/failure (not `navigator.onLine`). Registry search, marker selection, fly-to and the metric scale bar all work with local resources.
- **Controls**: navigation + compass, metric **scale bar**, reset-to-Peninsular-Malaysia, and the style selector.
- **Marker/popup/search polish**: subtle selected-marker pulse, a compact on-map popup (mnemonic · name · lifecycle · coordinate · Open), smooth fly-to, and an enriched side panel (adds **Coordinate**). Lifecycle semantics are retained — markers are never sized by load (no MVP-style load sizing).
- **Responsive**: desktop large-map + side details, tablet balanced, mobile bounded map height (no horizontal overflow); the accessible record list is always present.
- **Boundary overlay seam**: a future authoritative State-boundary overlay ([ADR-030](../adr/ADR-030-coordinate-assisted-state-resolution.md)) plugs in as an additional offline-served layer — **not** implemented here; no geometry fabricated.

**Dual-mode map (current):** the map shows the richest resources actually available — **rich mode** from a configured online style (`VITE_MAP_STYLE_*`) when it loads, else **neutral mode** using a small, committed, public-domain Natural Earth land/coastline/border geometry served app-relative (no external requests, works after clone+build). Substation markers, clusters, selection, details, search/filters, scale, reset, and the accessible list work in both modes. Mode detection is from real load success/failure (not `navigator.onLine`), bounded (no spinner/retry loop), with a user-triggered "Retry rich map" that preserves camera/selection/filters; status says "online geographic details unavailable" (never "offline"). The operator-installed **offline PMTiles Standard package (Phase E.1B)** is now **optional** (a locally hosted rich-basemap enhancement) and no longer required — missing PMTiles assets simply run neutral mode. Full detail in [engineering-map.md](engineering-map.md) §0 and §11b.

## Reference detail-workspace pattern for future registries

The map framework is registry-agnostic and reusable. Future registries (Circuit / Transformer / Relay / Sensitive Customer) reuse the same `[Table] [Map]` switch, the `EngineeringMap` framework with their own marker layer, and the same lightweight read-projection pattern.
