# GridDefence Changelog

This changelog records what has actually shipped, phase by phase, per
[`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md).
It is a factual record of implementation outcomes — not a design document.
Architecture rationale lives in `docs/architecture/` and `docs/adr/`;
day-to-day workflow lives in [`DEVELOPMENT.md`](DEVELOPMENT.md); review
criteria live in [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md).

Entries are added, never rewritten, as phases complete.

---

## Phase 3 — Equipment Registry (Circuit / CircuitTerminal Management)

**Scope:** Circuit and CircuitTerminal identity —
[`docs/architecture/equipment-registry-module.md`](docs/architecture/equipment-registry-module.md),
incorporating [ADR-006](docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
and [ADR-007](docs/adr/ADR-007-canonical-engineering-reference-object.md). This phase implements
Circuit & CircuitTerminal management specifically — not the full Equipment Registry module (load
transformers, auto-transformers, and relays remain unimplemented; see "Known limitations" below).

**Backend**

- `Circuit` (bay number, voltage level, line type, interconnector flag, operational status,
  remarks) and `CircuitTerminal` (one row per substation terminal — breaker number,
  commissioning date, remarks) as new persistence models, with `Circuit.bay_number` and
  `CircuitTerminal.breaker_number` deliberately separated per ADR-007's corrected field
  placement.
- A circuit is created with two or more terminals atomically; `CircuitTerminal` may be added
  later to extend a two-terminal circuit into a tee-off, using the same entity shape.
- `line_type` added as a new Core Platform reference table (Overhead Line / Cable / Submarine /
  Hybrid), following the exact `voltage_level` pattern.
- Full Router → Service → Repository → Models layering; `equipment_registry_audit_log` records
  every circuit-level field change and every terminal addition.
- `equipment_registry.read`/`equipment_registry.write` permissions registered and granted to the
  baseline Administrator/Engineer/Viewer roles, mirroring Substation Registry's own bootstrap.
- Migration `0004_equipment_registry_circuits` — hand-written, manually reviewed, and verified
  directly against real PostgreSQL (schema inspection, FK/unique-constraint verification,
  downgrade/upgrade reversibility).

**Frontend**

- `/circuits`, `/circuits/new`, `/circuits/:circuitId` — list (search/filter/paginate), create
  (dynamic terminal rows, minimum two, addable for tee-offs), and detail (edit, status change,
  add-terminal, audit log) pages, following Substation Registry's existing page/API-client
  conventions exactly.

**Tests**

- Backend: 27 new tests (service + bootstrap + API) covering two-terminal creation, tee-off/
  N-terminal creation, bay_number-vs-breaker_number field placement, validation failures
  (insufficient terminals, duplicate terminal substation, unknown substation, invalid reference
  data, invalid initial status), and search/filter/pagination — run against both SQLite and real
  PostgreSQL.
- Frontend: 10 new tests (list, create, detail pages) covering reference-data label resolution,
  the two-terminal minimum, tee-off extension, permission-gated write UI, and full-form
  submission.

**Known limitations**

- This phase does not implement the full Equipment Registry module — `LoadTransformerDetail`,
  `AutoTransformerDetail`, `RelayDetail`, `RelayControlledEquipment`, and the shared `Equipment`
  identity backbone those types would sit on (equipment-registry-module.md §7.1, §7.5, §7.8) are
  out of scope and unimplemented. `CircuitTerminal` carries its own identity directly rather than
  attaching to that backbone; see this phase's implementation report for the full reasoning.
- `EquipmentTopologyMap` (PSS/E correlation) and the scheme-module `circuit_id` migration
  (equipment-registry-module.md §7.10, §7.11) remain unimplemented, as documented — both were
  already sequenced to later phases before this implementation began.
- No manual browser UAT was performed for this phase; verification relied on the automated
  backend (SQLite + PostgreSQL) and frontend (lint/typecheck/test/build) suites.

### Phase 3 UAT follow-up — New Circuit button/empty-state fix, and a deployment gap found

**UAT defect 1 — missing create affordance.** `/circuits` had no visible way to create a circuit
and no helpful empty state when the database was empty. Fixed in `CircuitListPage.tsx`: a
prominent, permission-gated "New Circuit" button next to the page heading, and a genuine empty
state ("No circuits have been registered yet." + "Register your first circuit") shown only when
the circuit list is truly empty and no search/filter is active — distinct from the
filtered-empty-results case. 3 new frontend tests (navigation on click, empty state with/without
write permission); 2 existing tests updated for the renamed control.

**UAT defect 2 — the fix above didn't fix it; root cause was a missing deployment step, not
frontend code.** After the button/empty-state fix, the Administrator account still could not see
the write-gated controls. Root cause, confirmed by querying the live dev database directly:
`equipment_registry.read`/`equipment_registry.write` were never registered in `permission`, and
never granted to any role, because **no part of the application (no `main.py` startup hook, no
lazy bootstrap on login) ever invokes any module's `bootstrap.py` automatically** — every
module's permission catalog is registered only by manually running
`python -m app.modules.<name>.bootstrap` against the target database, a step that was previously
undocumented outside the automated test suite's own disposable-database fixtures. The frontend
was behaving correctly throughout, faithfully reflecting an incomplete backend deployment state.
Fixed by running `python -m app.modules.equipment_registry.bootstrap` against the dev database
(verified end-to-end via a live login + `GET /users/{id}/roles` call showing
`equipment_registry.write` now present for Administrator) and documenting the full required
seed/bootstrap sequence in README.md's new "Seeding and Bootstrapping" section, so this does not
recur for the next module or the next fresh environment.

**UAT defect 3 — same shape of bug again, in reference data this time.** The Line Type dropdown
on Create Circuit was empty. Investigation, in order: (1) `line_type` table exists on the dev
database — the Phase 3 migration ran correctly; (2) it had zero rows; (3) the other five
reference tables (`voltage_level`, `region`, `state`, `grid_owner`, `operational_status`) all held
their full, correct row counts, proving `python -m app.reference_data.seed` *had* been run at some
point — just before Phase 3 added `line_type` to it, and never re-run since; (4)/(5)/(6) the
backend endpoint, frontend API client, `useReferenceData` hook, and `CircuitCreatePage` were all
verified correct by inspection and by a live authenticated call to
`GET /api/v1/reference-data/line-types` — no code defect anywhere in that chain. Fixed by
re-running `python -m app.reference_data.seed` against the dev database (idempotent — it left the
other five tables untouched and inserted exactly the four missing `line_type` rows), confirmed via
direct SQL query and the same live API call afterward. No test or code change was needed — the
seed logic itself already had full, passing coverage (`app/reference_data/tests/test_seed.py`);
the gap was operational (a persistent database not re-synchronized after a code change), and is
now covered by the re-run guidance added to README.md's "Seeding and Bootstrapping" section.

### Phase 3 UAT fix package — commissioning date entry, full circuit edit, multi-voltage substations

Three must-fix items found during Phase 3 UAT before Phase 4 (PSS/E topology import) could begin,
implemented as one scoped fix package. See
[ADR-008](docs/adr/ADR-008-substation-voltage-yard.md) for the architecture decision.

**1. Commissioning date entry.** `CircuitTerminal.commissioning_date` was shown on the detail page
but had no input anywhere. Added to both `CircuitCreatePage`'s terminal rows and as an editable
field on the detail page (see item 2).

**2. Full circuit edit.** Circuit edit previously covered only `bay_number` and status; `line_type`
and `voltage_level` were already editable in the backend service (`update_circuit`) but not exposed
in the frontend form — added. Per-terminal `breaker_number`/`commissioning_date`/`remarks` editing
required a genuinely new backend capability (`EquipmentRegistryService.update_terminal`,
`PATCH /circuits/{id}/terminals/{terminal_id}`) — added, with its own audit trail
(`terminal_breaker_number`/`terminal_commissioning_date`/`terminal_remarks` fields). No DELETE
functionality was added, per the task's explicit constraint.

**3. Multi-voltage substation modeling.** The root cause the other two items were blocked behind:
`CircuitTerminal` referenced `Substation` directly, which cannot express which of a multi-voltage
substation's voltage levels (e.g. PKLG's own 275kV yard vs. its own 132kV yard) a circuit actually
terminates at. Added `SubstationVoltageYard` (owned by Equipment Registry, referencing Substation
Registry and Core Platform reference data only — no substation attributes duplicated) and changed
`CircuitTerminal.substation_id` to `CircuitTerminal.voltage_yard_id`. Business rule 6 (no duplicate
terminal on the same circuit) is now scoped to voltage yards, not substations — a circuit may
legitimately terminate twice at the same multi-voltage substation, once per voltage yard.

**Migration** (`0005_substation_voltage_yard`): creates `substation_voltage_yard`; backfills one
default yard per existing substation from that substation's own `voltage_level_id` (real, `NOT
NULL` on every existing row — the "no reliable voltage_level" fallback was not needed); repoints
every existing `circuit_terminal` row at its substation's new default yard; drops the old
`substation_id` column only after the new column is fully populated. Adds
`circuit_terminal.updated_at`/`updated_by_user_id` (backfilled from `created_at`/
`created_by_user_id`) to support terminal editability. Verified directly against the real,
persistent dev database (5 pre-existing substations → 5 yards; 4 pre-existing terminals correctly
repointed, confirmed by joining back to substation mnemonic and voltage level) — full
`upgrade → downgrade → upgrade` cycle run and re-verified against that same real data, not only in
the abstract. Downgrade restores `substation_id` by joining back through
`substation_voltage_yard`.

**New endpoints:** `GET/POST /api/v1/voltage-yards` (list, filterable by `substation_id`; create,
`equipment_registry.write`-gated); `PATCH /api/v1/circuits/{id}/terminals/{terminal_id}` (update).
`SubstationDetailPage` gained a "Voltage yards" section (list + add-yard form) — gated on
`equipment_registry.write`, not `substation_registry.write`, since voltage yards are owned by
Equipment Registry (ADR-008).

**Tests:** 46 new/updated backend tests (service + API), including a dedicated multi-voltage-
substation test class (`TestMultiVoltageSubstations`) proving a circuit may terminate twice at the
same substation across two different voltage yards; 168 backend tests total, passing against both
SQLite and real PostgreSQL. 12 new/updated frontend tests across `CircuitCreatePage`,
`CircuitDetailPage`, and `SubstationDetailPage`.

**Known limitation:** the voltage yard a terminal connects to is not editable after creation in
this fix package — only `breaker_number`/`commissioning_date`/`remarks`. Re-pointing a terminal to
a different yard was judged a materially different, out-of-scope operation.

### Phase 3 UAT validation fix — add-voltage-yard workflow was unusable, not just undiscoverable

UAT reported being unable to add a voltage yard from the Substation Detail page, despite the
button/form (added above) being present and permission-gated correctly. Root cause: the "New
voltage yard voltage level" dropdown offered *every* voltage level, including ones the substation
already had a yard at (most substations have exactly one, from the `0005` migration's backfill).
Picking one — the natural first attempt, since nothing distinguished available from taken — always
failed with `DuplicateVoltageYardError`, whose message embedded a raw internal `voltage_level_id`
("voltage level '4'") instead of a human-readable label, making a correctly-rejected duplicate look
like an unexplained, generic failure. The automated test written for this workflow in the previous
fix package coincidentally selected the one already-used voltage level in its own mock data and
still "passed," because the mock POST handler didn't enforce the real duplicate constraint the way
the actual backend does — masking the exact defect a real user hit.

**Fix:** (1) `DuplicateVoltageYardError` now takes the substation's mnemonic and the voltage
level's label, not raw ids — e.g. `"Substation 'PKLG' already has a voltage yard at '132kV'"`. (2)
Both add-voltage-yard forms (`SubstationDetailPage`, and `CircuitDetailPage`'s "Need a different
voltage yard?" mini-form) now filter the voltage-level dropdown to exclude levels already used by
the selected substation, and show a clear message ("already has a voltage yard at every known
voltage level") instead of an empty-looking form when none remain. Verified live against the real
dev database: reproduced the exact failing scenario, confirmed the new message, then confirmed a
valid creation succeeds and immediately appears in the global voltage-yard list Circuit Create/Edit
terminal selection reads from.

**Tests:** 1 new backend test assertion (human-readable duplicate message, both service- and
API-level); 5 new frontend tests — dropdown correctly excludes an already-used voltage level on
both forms, all-levels-exhausted empty state, and a newly-created yard becoming selectable in the
add-terminal dropdown without a page reload.

### Phase 3 UAT follow-up — `Substation.voltage_level_id` deprecated (ADR-009)

UAT found that `SubstationVoltageYard` (ADR-008) and `Substation.voltage_level_id` had become two
competing representations of the same fact. Substation Create still required a single voltage
level; List/Detail still displayed it as if authoritative even after a substation could hold
several voltage yards; and it was independently editable via `PATCH /substations/{id}` with no
relationship to the yards table at all, so the two could silently diverge.

**Fix (ADR-009):** `Substation.voltage_level_id` is deprecated, not dropped — the database column
stays (nullable, FK intact, no existing row's value touched) but is removed entirely from the API
contract (`SubstationCreate`/`Update`/`Summary`/`Detail`) and from both frontend forms. Substation
Create no longer asks for a voltage level; a new substation legitimately has zero voltage yards
until one is added via the existing `POST /voltage-yards` workflow. `SubstationVoltageYard` is now
the sole authoritative representation of a substation's voltage level(s), for both List and Detail.
The Substation List page composes this client-side (fetching Equipment Registry's
`GET /api/v1/voltage-yards` and grouping by `substation_id`), the same pattern `CircuitDetailPage`
already used — Substation Registry (Master Data) must never depend on Equipment Registry (Network
Data), so this is never a backend join (CLAUDE.md A2/F2). A substation with multiple voltage yards
now renders as e.g. "PKLG: 275kV, 230kV, 132kV, 500kV" instead of a single, potentially-stale value.

**Migration:** `0006_deprecate_substation_vlevel` — a single `ALTER COLUMN ... DROP NOT NULL`, no
data backfill (every existing row keeps its original value; only new rows are expected to be NULL
going forward). Verified against the real dev database: column confirmed nullable, all 7 existing
substations' legacy values confirmed untouched, and a substation created through the live API with
no `voltage_level_id` in the payload succeeded with the column landing `NULL` in PostgreSQL.

**Removed:** the Substation List "filter by voltage level" query parameter — nothing in this
project depended on it, and it would have silently given increasingly incomplete answers once new
substations stop populating the legacy column. Rebuilding it against voltage yards is deferred
to a later, separately-scoped piece of work if needed.

**Tests:** backend — `create_substation`'s signature no longer accepts `voltage_level_id`
(regression test), reference-data validation coverage moved to `region_id`; frontend — 4 new tests
(`SubstationCreatePage` no longer offers a voltage level field; `SubstationListPage` renders a
substation's voltage yards, including the multi-yard join case; `SubstationDetailPage` no longer
shows a standalone "Voltage level" field). 169 backend tests / 51 frontend tests passing.

### Phase 3 UAT follow-up — inline voltage yard creation removed from Circuit Detail (ADR-009 addendum)

UAT flagged that `CircuitDetailPage`'s "Need a different voltage yard?" section let a Circuit page
create `SubstationVoltageYard` rows directly — master topology data owned by the Substation
Registry workflow (per this ADR's main decision), created from a downstream, consuming module. The
ownership hierarchy is Substation → Voltage Yard → Circuit → Protection Scheme; a circuit should
consume voltage yards, not create them, and allowing it set a bad precedent for every future
topology entity (busbars, bus couplers, transformers, disconnectors, reactors, capacitors, PSS/E
import).

**Fix:** the entire "Need a different voltage yard?" section — substation select, voltage level
select, "Add voltage yard" button, and the supporting query/mutation logic
(`substationsQuery`, `addVoltageYardMutation`, `invalidateVoltageYards`) — is removed from
`CircuitDetailPage`. Voltage yard creation remains exclusively on the Substation Detail page. When
the "Add terminal" dropdown has no available voltage yard to offer, the page now shows static
guidance ("No suitable voltage yard exists for this circuit. Please add the required voltage yard
from the Substation Registry.") instead of a creation shortcut — helper text, not a navigation
link, per the explicit requirement that this stay a hard boundary.

**Architecture:** recorded as an addendum to ADR-009 (additive, not a rewrite of its existing
decision) generalizing the principle: *master data entities are created and managed only within
their owning module; dependent modules may reference them but must not create or modify them
inline without a compelling, separately-documented exception.* This applies to every future
topology entity, not only voltage yards.

**Tests:** 2 obsolete tests removed (mini-form dropdown filtering, newly-created-yard-becomes-
selectable — both exercised the now-removed inline creation path); 2 new tests added (confirms no
inline creation controls render at all; confirms the guidance text renders, and no "Add voltage
yard" button, when no voltage yard is available). Net test count unchanged (8 in this file, 51
frontend total). Backend untouched — `POST /api/v1/voltage-yards` still exists, still exclusively
reachable from the Substation Detail page's own workflow.

### Phase 3 close-out — terminal voltage-level guardrail and voltage yard metadata

Two final UAT-driven refinements before closing Phase 3.

**1. Terminal voltage-level guardrail (equipment-registry-module.md §9 rule 6a).** UAT found the
Add Terminal dropdown (Circuit Create and Circuit Detail) could offer a voltage yard at a
different voltage level than the circuit itself. A `Circuit` represents one physical transmission
line at one voltage class; enforced at the service layer on both `create_circuit` and
`add_terminal`, not only the frontend — a mismatched voltage yard submitted directly to the API
now returns a clear `TerminalVoltageLevelMismatchError`
(e.g. `"Voltage yard 'SIDST — 132kV' does not match this circuit's voltage level '500kV'"`).
`CircuitCreatePage` and `CircuitDetailPage` both filter their voltage-yard dropdowns to the
selected/current circuit voltage level.

**Architecture note:** this rule interacts with ADR-008's own rule-6 illustration (a circuit
terminating twice at the same multi-voltage substation, across two different voltage levels) —
combined with the existing one-yard-per-substation-per-level constraint, a single circuit can no
longer terminate twice at the same substation at all under the current model (no `Transformer`
equipment type exists yet to represent a same-site, cross-voltage connection). Recorded as an
addendum to ADR-008, not a rewrite; the conflicting test was replaced with an equivalent one using
two different substations at the same non-default voltage level.

**2. `SubstationVoltageYard` metadata — `commissioning_date`, `latitude`, `longitude`.** All
optional, and deliberately on the voltage yard, not the parent `Substation`: a multi-voltage site
may have yards commissioned at different dates with slightly different GIS coordinates. Migration
`0007_voltage_yard_metadata` adds the three nullable columns plus the same range/pair CHECK
constraints already established for `Substation`'s own geolocation fields, and
`updated_at`/`updated_by_user_id` for edit accountability (mirroring `CircuitTerminal`'s own
precedent). No data backfill — every existing row remains valid with `NULL` metadata. New
`PATCH /api/v1/voltage-yards/{id}` endpoint supports partial updates (Ellipsis-sentinel pattern,
consistent with every other partial-update endpoint in this codebase). `SubstationDetailPage`'s
voltage yard list now displays and lets an authorized user edit each yard's metadata inline; the
add-voltage-yard form accepts all three fields optionally.

**Known limitation:** voltage yard metadata edits are tracked via `updated_at`/`updated_by_user_id`
only, not a field-level audit log (unlike `Substation`/`Circuit`'s own attribute changes) — judged
proportionate for this incremental addition; a full `substation_voltage_yard_audit_log` can be
added later analogous to the existing audit log pattern if required.

**Tests:** backend — 4 new service tests + 2 new API tests for the terminal-voltage-level
guardrail (create-circuit rejection, add-terminal rejection, human-readable message, valid
non-default-level circuit still succeeds); 8 new service tests + 5 new API tests for voltage yard
metadata (create/update/partial-update/clear/geo-pair validation/range validation/not-found).
1 pre-existing backend test rewritten (its cross-voltage-level scenario is no longer constructible
under rule 6a). Frontend — 2 new tests on `CircuitCreatePage` (no yard offered before a voltage
level is chosen; dropdown filtered per selected level) replacing 1 obsolete test, 1 new test on
`CircuitDetailPage` (excludes a mismatched-level yard), 4 new tests on `SubstationDetailPage`
(metadata submitted on create, metadata displayed and editable, read-only without
`equipment_registry.write`). 190 backend tests / 56 frontend tests passing (SQLite, real
PostgreSQL, and lint/typecheck/build all clean).

### Phase 3 freeze package — bay number semantics, canonical circuit naming, Switchyard terminology

Five final UAT/architecture cleanup items before freezing Phase 3.

**1. Bay number semantics.** Users were unsure whether to enter "1" or "Line 1" for `bay_number`.
Decision: it is a bay/circuit *designator* only ("1", "2", "Main", "Transfer"), never a route
description. UI placeholders/labels updated (`CircuitCreatePage`/`CircuitDetailPage`/
`CircuitListPage`); deliberately **no** numeric-only validation added, since real bay designators
are frequently non-numeric.

**2 & 3. Duplicate circuit-number display and canonical circuit naming.** Investigation confirmed
`circuit_name` is fully computed, never stored (`EquipmentRegistryService._compute_circuit_name`)
— so both defects were fixable with zero migration. Root causes: (a) the computed name embedded
`bay_number` (e.g. `"PKLG–IGBK Line 1"`), which duplicated visually against a separately-displayed
`bay_number` field; (b) terminal mnemonics were joined in terminal-insertion order, so the same
physical circuit could display as `"PKLG–IGBK"` or `"IGBK–PKLG"` depending on which terminal was
entered first. Fix: `_compute_circuit_name` now takes only the terminal mnemonics, sorted
alphabetically (case-insensitive), and never appends `bay_number`. `CircuitDetailPage` now shows
"Circuit: {name}" and a separately-labeled "Bay / Circuit No." field, never combined.

**Architecture conflict found and resolved:** the new canonical-naming rule interacts with rule 6a
(the terminal voltage-level guardrail added in the prior fix package) in a way that makes ADR-008's
own rule-6 illustration (a circuit terminating twice at the same multi-voltage substation, across
two voltage levels) no longer constructible — combined with the one-yard-per-substation-per-level
constraint, a single circuit can no longer terminate twice at the *same* substation at all under
the current model (no `Transformer` equipment type exists yet). Recorded as a new business rule 6a
in `equipment-registry-module.md` §9 and an ADR-008 addendum; the one pre-existing test relying on
the old scenario was replaced with an equivalent one using two different substations.

**4. "Voltage Yard" vs "Switchyard" terminology.** Recommendation: keep internal model/table/
column/API names unchanged (`SubstationVoltageYard`, `substation_voltage_yard`, `voltage_yard_id`,
`/api/v1/voltage-yards`); adopt **"Switchyard"** as the user-facing term in UI labels, buttons, and
user-facing error messages (`VoltageYardNotFoundError`, `DuplicateVoltageYardError`,
`TerminalVoltageLevelMismatchError` message text updated); architecture docs use "Voltage Yard /
Switchyard" to bridge existing terminology. A full rename (table + FKs + every reference across two
modules and three ADRs) was judged disproportionate churn for a naming-only change. Recorded as an
ADR-008 addendum.

**5. Architecture document finalized.** `equipment-registry-module.md` gained a new "Phase 3 Final
Model Summary" section (conceptual hierarchy diagram, terminal voltage-level guardrail, ADR-009's
master-data ownership principle, `Substation.voltage_level_id` deprecation summary, canonical
naming rule, `bay_number` semantics, explicit note that transformers/busbars/bays remain future
scope) plus corrected §7.4/§7.6 definitions, an updated Glossary, and three new Appendix entries.

**Migration impact:** none — every change in this package is code/UI/documentation only.

**Tests:** backend — 2 rewritten (naming format), 1 new (deterministic ordering regardless of
terminal entry order); frontend — 1 rewritten test replaced with 2 (`CircuitCreatePage`), 1 new
regression test (`CircuitListPage`, proving the route name and bay number never duplicate), test
label/text updates across `CircuitCreatePage`/`CircuitDetailPage`/`SubstationDetailPage`/
`CircuitListPage` for the Switchyard terminology and new naming format. 191 backend tests / 57
frontend tests passing (SQLite, real PostgreSQL, and lint/typecheck/build all clean).

---

## Phase 2 — Substation Registry

**Scope:** The platform's master data anchor —
[`docs/architecture/substation-registry.md`](docs/architecture/substation-registry.md).

**Backend**

- `Substation`, `SubstationAlias`, `SubstationAuditLog` — model, repository,
  service, router, wired to Phase 1's IAM (`getUser`/`hasPermission`,
  `require_permission("substation_registry.write")`) for accountability and
  authorization.
- A shared, read-only Core Platform reference-data API
  (`app/reference_data/router.py`) — not owned by Substation Registry, added
  as a necessary prerequisite for populating create/edit form dropdowns,
  reusable by every future module.
- `substation_registry.read`/`substation_registry.write` permission codes
  registered in IAM's catalog and granted to the baseline
  Administrator/Engineer/Viewer roles.
- Alembic migration `0003_substation_registry`.

**Frontend**

- Substation list (TanStack Table, with region/status filtering and search),
  detail/edit view, create form, and status-change control, under
  `frontend/src/modules/substation_registry/`.

**Tests:** 45 backend service/bootstrap tests + 9 API contract tests + 8
frontend tests, covering mnemonic uniqueness (case-insensitive, incl.
historical-alias reuse), `substation_id` immutability, alias creation on
mnemonic change, geolocation pair validation, and soft-delete-only
enforcement.

**Architectural issue flagged, not resolved at the time:** substation-registry.md
§10's lifecycle diagram omitted the `UNDER_CONSTRUCTION` status entirely and
showed no direct `Active → Decommissioned` edge. Resolved conservatively for
this phase (closed allow-list of only the drawn edges) and explicitly
flagged for follow-up — see below.

### Phase 2 follow-up — lifecycle resolution and PostgreSQL verification

**Operational status lifecycle resolved via [ADR-005](docs/adr/ADR-005-substation-operational-status-lifecycle.md).**
substation-registry.md §10 revised to a seven-edge closed transition graph
restoring `Under Construction` to active use
(`Planned → Under Construction → Active`) and adding a direct
`Active → Decommissioned` edge (mothballing is not a mandatory
precondition of decommissioning). `Planned → Active` directly is no longer
legal — a behavioural change from this phase's original interim
implementation. Backend allow-list and 20 status-transition tests updated;
no frontend changes were needed (the UI never replicated the transition
graph client-side, by design — CLAUDE.md A12).

**PostgreSQL environment established as a permanent part of local
development** — dedicated `engineering_platform` database and
least-privileged `engineering_app` role (never the default `postgres`
database/superuser), documented in full in
[`docs/development/postgresql-setup.md`](docs/development/postgresql-setup.md).
A real, pre-existing configuration bug was found and fixed in the process:
`backend/app/core/config.py`'s `env_file=".env"` was a relative path,
resolved against the process's current working directory — meaning the
documented root `.env` was never actually read during local (non-Docker)
backend runs (`cd backend && uvicorn ...`/`pytest`), only during Docker
Compose (which injects real environment variables directly, bypassing the
file entirely). Fixed by resolving `.env` via an absolute path computed from
`config.py`'s own location.

**Full verification against real PostgreSQL 18** (migrations 0001–0003,
schema inspection, full pytest suite, `downgrade -1`/`upgrade head`
reversibility) — see `docs/development/postgresql-setup.md` §9 for the
opt-in `GRIDDEFENCE_TEST_DATABASE_URL` mechanism added to
`backend/conftest.py` to make this repeatable. Found and fixed one genuine
PostgreSQL-only defect: `voltage_level_id=99999` (and equivalent
out-of-range reference-data ids) is silently accepted by SQLite's flexible
integer typing but raises an unhandled `psycopg.errors.NumericValueOutOfRange`
on PostgreSQL's real `SMALLINT` columns — would have surfaced as a raw 500
error in production, never caught by SQLite-only testing. Fixed in
`app/reference_data/repository.py` by treating any id outside `SMALLINT`'s
representable range as "not found" before it reaches the database.

### Phase 2 UAT — ACCEPTED

Manually verified end-to-end through `localhost` against the real
PostgreSQL `engineering_platform` database (not SQLite) — see
`docs/development/postgresql-setup.md` for how that environment is set up.
Tested:

- Backend starts successfully.
- Frontend starts successfully.
- Login with the bootstrap Administrator account works.
- Substations page is accessible.
- Create substation works.
- Editing a substation's official name and mnemonic works.
- The created row is visible directly in the PostgreSQL table.
- Duplicate-mnemonic and duplicate-name validation both correctly reject.

**Phase 2 (Substation Registry) is ACCEPTED.** All required backend/frontend
tests pass, the operational status lifecycle gap is resolved (ADR-005), the
schema is verified against real PostgreSQL, and manual UAT confirms the
end-to-end flow works as built.

---

## Phase 1 — IAM + Core Reference Data

**Scope:** Identity and Access Management (local authentication only) and
the Core Platform reference/lookup tables, per
[`docs/architecture/iam-module.md`](docs/architecture/iam-module.md),
[`docs/adr/ADR-002-identity-and-access-management.md`](docs/adr/ADR-002-identity-and-access-management.md),
and `substation-registry.md` §6.

**Backend**

- IAM data model: `User`, `UserCredential`, `Role`, `Permission`,
  `RolePermission`, `UserRole`, `ExternalIdentityMapping`, `IAMAuditLog`.
- IAM service layer implementing the five interfaces named in
  `iam-module.md` §13: `hasPermission()` (fail-closed), `getUser()`,
  `resolveExternalPrincipal()`, `assertDifferentActors()`,
  `listUserRoles()` — plus user/role/permission CRUD and grant/revoke
  orchestration, each with audit writes.
- Local username/password authentication only. LDAP, Active Directory,
  OAuth, OIDC, MFA, and SSO are explicitly out of scope for this phase
  (structurally supported by `ExternalIdentityMapping`, not implemented).
- A stateless, HMAC-SHA256-signed bearer access token
  (`app/modules/iam/security.py`) — chosen because `iam-module.md` §4
  scopes the token mechanism itself as an implementation detail outside
  architectural scope, and no `Session` entity exists among IAM's owned
  entities.
- Idempotent bootstrap of the initial Administrator account, the baseline
  `Administrator`/`Engineer`/`Viewer` roles, and IAM's own permission
  catalog (`app/modules/iam/bootstrap.py`) — the bootstrap Administrator
  self-references its own `user_id` as creator and audit actor, a stronger
  realization of "never a null actor" than the architecture's stated
  minimum.
- Core Platform reference data: `voltage_level`, `region`, `state`,
  `grid_owner`, `operational_status`, seeded by an idempotent script
  (`app/reference_data/seed.py`).
- Alembic migration `0002_iam_and_core_reference_data` — hand-written (no
  live PostgreSQL reachable in the implementation environment to
  autogenerate against), manually reviewed, verified via `alembic upgrade
  head` → schema inspection → `alembic downgrade base` against a
  throwaway SQLite database as a stand-in.

**Frontend**

- Local login page, current-user display and sign-out (`AppShell`), role
  management, permission catalog management, and user↔role assignment
  UI, under `frontend/src/modules/iam/`.
- Client-side route gating (`ProtectedRoute`) and UI-only permission
  gating derived from the current user's granted permissions — the
  backend remains the sole authorization authority (CLAUDE.md A12); the
  frontend gate only decides what to *show*, never what to *allow*.

**Tests**

- Backend: 47 pytest tests covering fail-closed `hasPermission()`,
  username/role-name/external-identity uniqueness, role lifecycle
  (retired-role guard, revoke-not-delete, idempotent grants),
  authentication, bootstrap idempotency, reference data seed idempotency,
  and API-contract-level authorization enforcement.
- Frontend: 16 Vitest tests covering login success/failure, session
  handling (including a fix for a defect this test suite caught — see
  below), route protection, and permission-gated management UI.

**Defects found and fixed during this phase**

- A SQLite-only autoincrement incompatibility on reference-table primary
  keys (SQLite requires a literal `INTEGER PRIMARY KEY` for its
  rowid-autoincrement behaviour; `SMALLINT PRIMARY KEY` does not qualify)
  was found via the seed-idempotency test and fixed with a
  dialect-variant column type (`SMALLINT` on PostgreSQL, `INTEGER`
  elsewhere) applied identically to both the SQLAlchemy model and the
  Alembic migration.
- The frontend session handler originally cleared a valid access token on
  *any* failure of the `/users/me` request, including transient network
  errors — meaning a brief outage could silently sign a user out. Fixed
  to clear the token only on an explicit `401 Unauthorized` response;
  covered by a regression test.

**Known limitations**

- No Docker and no local PostgreSQL instance was reachable in the
  implementation environment; both the migration and the full test suite
  were verified against SQLite as a documented stand-in. The migration
  should still be run once against real PostgreSQL before being treated
  as final.
- Frontend styling is intentionally minimal — this phase prioritized
  correctness over visual design.

**Architectural issue surfaced**

- `implementation-plan.md` §6 mentions seeding "the MVP's grid codes,"
  but `substation-registry.md`'s canonical schema (the authoritative
  source for this phase) defines no `grid` table. Flagged during
  implementation and resolved by following `substation-registry.md`
  exactly — only the five documented reference tables were seeded, using
  region groupings rather than grid codes.

---

## Phase 0 — Repository Foundation

**Scope:** Project skeleton, tooling, and infrastructure — no business
modules — per `docs/architecture/implementation-plan.md`'s Phase 0
section.

**Backend**

- FastAPI application skeleton with an unversioned `/health` check and an
  empty versioned `/api/v1` router that later phases attach module
  routers to.
- SQLAlchemy `Base` declarative model shared by every future module.
- Alembic initialized with a single no-op baseline revision
  (`0001_initial_baseline`) establishing the migration chain without
  creating any domain tables.
- `backend/pyproject.toml` established as the single source of truth for
  backend dependencies (no `requirements.txt`); Ruff configured for
  linting and formatting; Pytest configured with per-module test
  discovery.
- Empty module packages created for every module named in
  `implementation-plan.md` §2 (`__init__.py` only) — no business logic.

**Frontend**

- Vite + React + TypeScript skeleton: `AppShell`, a `StatusPage` proving
  connectivity to the backend `/health` endpoint through TanStack Query,
  and a minimal `StatusBadge` UI primitive.
- `frontend/package.json` established as the single source of truth for
  frontend dependencies; ESLint, TypeScript strict checking, and Vitest
  configured.
- `src/modules/` established as the convention every future business
  module's frontend feature folder lands in.

**Infrastructure**

- `docker-compose.yml` defining `postgres`, `backend`, and `frontend`
  services — Postgres 16 with a persisted named volume, backend waiting
  for Postgres health before starting. The host's `.venv` is never
  mounted into any container.
- Project-local Python virtual environment convention established:
  `.venv` at the repository root, no global installs, `pip install -e
  "./backend[dev]"` as the standard setup command.
- `.env.example` documenting every environment variable with defaults; no
  secrets committed to source control.

**Tests**

- Backend smoke tests confirming the app starts and `/health` responds
  correctly, and that settings load from the environment without error.
- Frontend smoke test confirming the app shell renders the status page
  without crashing.

**Known limitations**

- No business logic, no domain models beyond Alembic's baseline revision,
  and no API endpoints beyond `/health` — by design, this phase is
  infrastructure only.
