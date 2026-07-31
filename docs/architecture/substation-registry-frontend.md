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
