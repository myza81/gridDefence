# GridDefence Changelog

This changelog records what has actually shipped, phase by phase, per
[`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md).
It is a factual record of implementation outcomes — not a design document.
Architecture rationale lives in `docs/architecture/` and `docs/adr/`;
day-to-day workflow lives in [`DEVELOPMENT.md`](DEVELOPMENT.md); review
criteria live in [`REVIEW_CHECKLIST.md`](REVIEW_CHECKLIST.md).

Entries are added, never rewritten, as phases complete.

---

## Phase 4 — PSS/E Integration

**Scope:** RAW file import infrastructure —
[`docs/architecture/psse-integration-module.md`](docs/architecture/psse-integration-module.md),
[ADR-003](docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md) (topology/load
separation), [ADR-006](docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
and [ADR-007](docs/adr/ADR-007-canonical-engineering-reference-object.md)
(`EquipmentTopologyMap`). Implements only PSS/E import/preview/commit/activate and
`EquipmentTopologyMap` correlation — Network Model, UFLS, UVLS, and scheme assignment logic remain
explicitly out of scope, per the task's own instruction.

**Mandatory pre-implementation step.** Before any parser or model code was written, the two real
sample RAW files at `docs/samples/psse/` (`110226n.raw` — full topology + load, rev 34; and
`PSSE_LOAD_20260608_1730.raw` — load-only, abbreviated field shape) were inspected directly
(section ordering, exact field layouts, terminator conventions, comment syntax) and findings
presented before implementation began, per the task's explicit mandate to design against real
files rather than generic PSS/E documentation. Two concrete, non-obvious findings drove the
parser's design: (1) LOAD DATA appears in **two different shapes** in real files — a 17-field
standard shape and a 7-field abbreviated shape sharing fields 0-6 — and a third, genuinely valid
"no reading" 2-field shape (`I,'ID' / No Reading / ...`) that is not malformed data, just a meter
with nothing to report that cycle; (2) the load-only sample has **zero header lines, zero bus
records, and inconsistent/out-of-sequence section terminator labels**, so section tracking is done
purely by counting terminator lines in the order they appear, never by matching a fixed, closed
list of expected section names — an unrecognized section is tolerated (warned, not fatal).

**Backend**

- New module `app/modules/psse_integration/`: `models.py` (`RawFileImportBatch`,
  `TopologyVersion`, `TopologyBus`, `TopologyBranch`, `TopologyTransformer`, `LoadSnapshot`,
  `LoadSnapshotBusState`, `LoadSnapshotElementState`, `NetworkLoad`, `NetworkGenerator`,
  `EquipmentTopologyMap`, `PsseImportAuditLog`), `raw_parser.py`, `signature.py`, `matching.py`,
  `repository.py`, `service.py`, `schemas.py`, `exceptions.py`, `dependencies.py`, `router.py`,
  `bootstrap.py`, `jobs.py`.
- **Topology/load separation is structural (ADR-003), not a naming convention:**
  `TopologyBus`/`TopologyBranch`/`TopologyTransformer` carry no P/Q, voltage, or in-service field
  anywhere — that data lives exclusively on `LoadSnapshotBusState`/`LoadSnapshotElementState`/
  `NetworkLoad`/`NetworkGenerator`. This guarantees, by construction, that momentary operational
  state can never leak into the deterministic topology signature.
- **Deterministic topology signature** (`signature.py`): a SHA-256 hash over canonicalized
  (sorted, fixed-6-decimal-formatted) bus/branch/transformer records, with branch/transformer
  endpoints sorted so PSS/E's arbitrary from/to ordering never affects the hash. Re-importing a
  structurally identical file reuses the existing `TopologyVersion` rather than creating a
  duplicate.
- **Preview → Commit → Activate workflow**, all through the service layer: Preview
  (`PsseIntegrationService.preview`) is genuinely zero-persistence — no database row is ever
  created. Commit persists a `RawFileImportBatch`, `TopologyVersion`/`LoadSnapshot` (or reuses an
  existing `TopologyVersion` by signature), but never marks anything Current. Activate is a
  separate, explicit, privileged action (`psse_integration.activate`) that atomically promotes a
  batch's `TopologyVersion`/`LoadSnapshot` to `Current`, automatically superseding whatever was
  previously Current — the lighter `Imported → Current → Superseded` lifecycle (ADR-003),
  deliberately distinct from CLAUDE.md A3's canonical engineering version lifecycle.
- **Flexible import types**, detected purely from parsed content (bus-record count present or
  absent), never from filename or user assertion: `FULL_TOPOLOGY_WITH_LOAD` creates/reuses a
  `TopologyVersion` and always extracts a `LoadSnapshot` from the same file; `LOAD_ONLY` requires
  an existing Current `TopologyVersion` to target (raises `NoCurrentTopologyVersionError`
  otherwise) and creates only a `LoadSnapshot`, matching loads by PSS/E bus number.
- **`EquipmentTopologyMap`** targets `CircuitTerminal` directly (never `Circuit`, never a generic
  `Equipment` id — this codebase's real Phase 3 build has no generic Equipment backbone, so
  ADR-007's terminology was adapted to the actual schema). Matching (`matching.py`, a pure,
  ORM-free function) is computed automatically whenever a *new* `TopologyVersion` is created:
  for each `CircuitTerminal`, candidates are PSS/E elements connecting that terminal's substation
  to any *other* terminal's substation within the same `Circuit` (generalizes to tee-offs with no
  special-casing); disambiguated by exact `ckt_id`-vs-`bay_number` match. Zero candidates →
  `unmatched`; exactly one exact match → `clean_match`; anything ambiguous or mismatched →
  `discrepancy`, never guessed. `ENTERED_IN_ERROR` circuits/terminals are excluded from matching
  candidates entirely. Resolving a discrepancy (`resolve_discrepancy`) only records the engineer's
  classification on this module's own table — it never writes to Equipment Registry, since the
  real `CircuitTerminal.voltage_yard_id` has no edit path after creation to write to.
- **Redis + RQ** introduced for the first time in this project (`app/core/queue.py`,
  `app/worker.py`) for async RAW parsing/validation. `settings.rq_async` (new config field,
  default `True`) set to `False` in the test environment (`backend/conftest.py`) runs jobs
  synchronously, in-process, against a `fakeredis` connection — no real Redis server needed for
  correctness tests. `jobs.py` contains the only code in this module that opens its own database
  session (`SessionLocal`), since RQ jobs run in a worker process outside any FastAPI request
  context.
- New endpoints under `/api/v1/psse-integration`: `POST /imports/preview`, `POST /imports/commit`
  (both return a job id; parsing runs async), `GET /imports/jobs/{id}` (poll), `GET/GET
  /imports/batches[/{id}]`, `POST /imports/batches/{id}/activate`, `GET/GET
  /topology-versions[/{id}]`, `POST /topology-versions/{id}/recompute-matching`, `GET/GET
  /load-snapshots[/{id}]`, `GET /current-status`, `GET
  /topology-versions/{id}/equipment-map`, `POST /equipment-map/{id}/resolve`, `GET
  /circuits/{id}/correlation`. New permissions: `psse_integration.read` (open to any authenticated
  user, matching this project's existing read-permission precedent), `psse_integration.import`
  (Administrator + Engineer), `psse_integration.activate` (Administrator only — activation is
  "explicit, privileged, atomic, and audited").
- Migration `0012_psse_integration` — hand-written, manually reviewed, fully reversible (verified
  `upgrade → downgrade → upgrade` against real PostgreSQL). One genuine design issue found and
  fixed before the migration was written: `raw_file_import_batch` ↔ `topology_version` ↔
  `load_snapshot` forms a real 3-table foreign-key cycle (a batch points forward at the
  TopologyVersion/LoadSnapshot it produced; those point back at the batch that created them) —
  resolved with `use_alter=True` on the batch's two forward-pointing columns, closing the cycle via
  a separate `ALTER TABLE` once all three tables exist, both in the SQLAlchemy models and the
  migration.
- `python-multipart` added as a new dependency (required by FastAPI for the RAW file upload
  endpoints — the first file-upload endpoints in this project).

**Frontend**

- New module `frontend/src/modules/psse_integration/` (`types.ts`, `api.ts`,
  `useJobPolling.ts`) plus 5 pages under `pages/`: `PsseImportUploadPage` (file select, preview,
  commit — polls the async job until terminal), `PsseImportHistoryPage` (paginated batch list),
  `PsseBatchDetailPage` (batch detail + Activate control, permission-gated), `PsseCurrentStatusPage`
  (current TopologyVersion/LoadSnapshot summary), `PsseEquipmentTopologyMapPage` (clean-match/
  unmatched/discrepancy review, with an Accept/Reject resolution form for discrepancies).
- `apiClient` gained a `postForm` method (multipart upload, no `Content-Type` override so the
  browser sets its own boundary) — the first file-upload support in the shared API client.
- Wired into `router.tsx` (`/psse-integration/import`, `/history`, `/batches/:batchId`,
  `/current-status`, `/topology-versions/:id/equipment-map`) and `AppShell.tsx`'s nav.

**Tests**

- Backend: 55 new tests across `test_raw_parser.py` (16, including direct integration tests
  against the real sample files — bus/branch/transformer counts, both 2- and 3-winding
  transformers, voltage solution extraction, "no reading" load handling, unknown-section
  tolerance), `test_signature.py` (7 — determinism, record-order and endpoint-order independence),
  `test_matching.py` (8 — clean-match/unmatched/discrepancy, case-insensitive ckt_id matching,
  tee-off generalization, cross-circuit isolation), `test_service.py` (16 — preview zero-
  persistence, topology reuse vs. new, load-only against Current, activation atomicity and
  supersession, ENTERED_IN_ERROR exclusion, discrepancy resolution and re-resolution rejection,
  circuit correlation), `test_jobs.py` (4), `test_bootstrap.py` (6), plus
  `tests/test_psse_integration_api.py` (8 — auth/RBAC, full preview→commit→activate HTTP flow via
  RQ running synchronously against `fakeredis`). 351 backend tests total, passing against both
  SQLite and real PostgreSQL.
- Frontend: 15 new tests across the 5 new pages plus 1 new `apiClient.postForm` test. 118 frontend
  tests total, passing; lint/typecheck/build all clean.
- **One genuine PostgreSQL-only defect found and fixed**, exactly the kind SQLite-only testing
  cannot catch: `psse_import_audit_log.entity_id` was `String(64)`, but
  `EquipmentTopologyMap`'s own audit entries key on a composite
  `"{topology_version_id}:{circuit_terminal_id}"` string (two UUIDs + separator = 73 characters) —
  SQLite silently accepts an over-length `VARCHAR`; PostgreSQL correctly raised
  `StringDataRightTruncation`. Fixed by widening the column to `String(80)` in both the model and
  the (still-unmerged) migration, then re-verified against real PostgreSQL.

**Known limitations**

- No manual browser UAT was performed for this phase — no browser automation tool was available in
  the implementation environment. Verification relied on the automated backend (SQLite + real
  PostgreSQL) and frontend (React Testing Library + lint/typecheck/build) suites, plus direct
  `alembic upgrade/downgrade/upgrade` verification against the real dev PostgreSQL database.
  Redis/RQ's real, non-`fakeredis` production path (`app.worker`, a genuine background worker
  process against a real Redis server) was not separately smoke-tested — only its `docker-compose.yml`
  wiring and the `rq_async=True` code path (exercised by every non-test run) were reviewed for
  correctness.
- The substation-to-bus matching heuristic (`_match_substation_for_bus`, matching a bus name's
  leading 4 characters against `Substation.mnemonic`, case-insensitively) is deliberately simple
  and documented as such — not a claim of perfect fidelity against every possible real PSS/E
  naming convention.
- The parser supports PSS/E RAW revision 34 only, as scoped — section boundaries are tracked by
  terminator-line counting rather than a fixed section list specifically so a future revision's
  differently-ordered or additional sections degrade to warnings rather than breaking existing
  parsing, but no second revision was implemented or tested against.
- A future Network Model module is the intended consumer of `get_circuit_correlation`
  (union-of-terminals resolution) — that module itself is out of this phase's scope, so this
  endpoint currently has no real caller beyond its own test coverage and the review UI.

---

## Phase 3.5 — Transformer Registry

**Scope:** `Transformer`/`TransformerTerminal` identity, inserted between Equipment Registry
(Phase 3) and PSS/E Topology Import (Phase 4) because a transformer is a fundamental topology
element defining connectivity between two voltage levels —
[`docs/architecture/equipment-registry-module.md`](docs/architecture/equipment-registry-module.md)'s
new "Phase 3.5 Addendum: Transformer Registry" section. Tertiary windings, transformer impedance,
tap-changer modelling, transformer loading, and protection-relay modelling remain explicitly out of
scope.

**Architecture Decision Gate.** Following the same architecture-first process used for Phase 3,
three genuine modelling ambiguities were presented with options and a recommendation before any
code was written, and implementation began only after explicit approval of all three: (1)
`TransformerTerminal` child rows (`side` = HV/LV) over direct `hv_*`/`lv_*` columns on
`Transformer`, mirroring `CircuitTerminal`'s own precedent, for future tertiary-winding
compatibility; (2) the generated engineering short name (e.g. `SGT1`) computed at read time, never
stored, for the identical reason `Circuit`'s own canonical name is computed rather than stored; (3)
uniqueness keyed on `(hv_switchyard_id, lv_switchyard_id, transformer_number)` — representing the
*physical transformer's* identity — deliberately distinct from the generated short name, which is a
separate, computed, user-facing label two physically distinct transformers at different substations
may legitimately share.

**Backend**

- `Transformer` (transformer number, capacity, commissioning date, operational status, type,
  manufacturer, remarks) and `TransformerTerminal` (one HV row, one LV row per transformer — each
  with its own breaker number) as new persistence models, plus `transformer_audit_log` as this
  entity family's own audit trail (CLAUDE.md A4).
- The engineering short name (`XGT1`, `SGT1`, `T1`, ...) is computed at read time from the HV
  terminal's voltage level, using a TNB prefix convention (500kV→`XGT`, 275/230kV→`SGT`,
  132/33/22/11kV→`T`) — never stored, never accepted on create/update.
- Business rules enforced at the service layer: exactly one HV and one LV terminal; HV voltage
  level strictly higher than LV; HV and LV terminals cannot connect to the same switchyard; HV and
  LV may belong to the same or different substations; a switchyard pair plus transformer number
  must be unique (checked via a repository query joining `TransformerTerminal` twice via
  `sqlalchemy.orm.aliased`, not a raw database constraint, per CLAUDE.md §11.8 — the identity spans
  two child rows a single-table `UNIQUE` constraint cannot express); a transformer's switchyards
  are immutable after creation.
- `voltage_level` reference data extended with 33kV, 22kV, and 11kV (previously only
  500/275/230/132kV existed) — the LV-side distribution voltage classes the short-name prefix table
  and breaker-suggestion formulas name explicitly.
- `equipment_registry.read`/`equipment_registry.write` permissions reused as-is — no new permission
  introduced.
- New endpoints: `GET/POST /api/v1/transformers`, `GET/PATCH /api/v1/transformers/{id}`,
  `GET /api/v1/transformers/{id}/audit-log` (the last one beyond the originally-specified four
  endpoints, added for consistency with Circuit's own audit-visibility pattern — a hard CLAUDE.md
  auditability requirement, not optional polish). No `DELETE` endpoint.
- Migration `0008_transformer_registry` — hand-written, manually reviewed, fully reversible, no
  data backfill (new tables, no pre-existing rows). Verified directly against real PostgreSQL
  (`alembic upgrade head`, schema inspection of all three new tables) and via live `curl` smoke
  testing against a running server on the real dev database (create, duplicate rejection, and
  reversed-voltage-order rejection all returned the expected human-readable errors).

**Frontend**

- `/transformers`, `/transformers/new`, `/transformers/:transformerId` — list (search/filter/
  paginate), create, and detail (inline edit, audit log) pages, following Circuit Registry's exact
  page/API-client conventions and UX pattern (list + create + detail-with-inline-edit, no separate
  edit route).
- Breaker-number suggestion (`suggestBreakerNumber`) — a pure, frontend-only function implementing
  the five given formulas (275kV: `H{N}0`; 230kV: `{N}H0`; 132kV: `{N}10`; 33kV/22kV: `{N}T0`;
  11kV: `3{N}`; no formula for 500kV, an intentional spec gap). Triggered once the HV/LV switchyard
  and transformer number are chosen; always freely overridable; the backend never validates or
  enforces breaker-number format.

**Tests**

- Backend: 42 new tests (29 service + 13 API) covering two-terminal creation, the generated
  short-name computation (parametrized across all 7 voltage levels), HV/LV voltage-order and
  same-switchyard rejection, same-substation-different-switchyard allowance, uniqueness rejection
  and parallel-transformer allowance, breaker-number override never rejected, search/filter, edit,
  and permission enforcement. 233 backend tests total, passing against both SQLite and real
  PostgreSQL.
- Frontend: 22 new tests (list, create, detail pages, plus the breaker-suggestion pure function)
  covering the generated short name display, auto-suggested and freely-overridable breaker numbers,
  list/detail rendering, edit submission, and permission-gated create/edit controls. 79 frontend
  tests total, passing; lint/typecheck/build all clean.

**Known limitations**

- No manual browser UAT was performed for this phase — no browser automation tool was available in
  the implementation environment. Verification relied on the automated backend (SQLite + real
  PostgreSQL) and frontend (React Testing Library simulating real DOM rendering, user interaction,
  and form submission against mocked network calls, plus lint/typecheck/build) suites, together
  with live `curl` smoke testing of the real backend API against the real dev database.
- `transformer_type` is free text, not a reference table — no fixed vocabulary was specified, and
  inventing one was judged out of scope (CLAUDE.md: "Claude must not invent business rules").
- No transition-legality graph is asserted for `Transformer.operational_status_id`, unlike
  `Circuit`'s own dedicated status-change endpoint — `operational_status_id` is a plain field on the
  general `PATCH` endpoint, since no transition rule was specified for transformers.

### Phase 3.5 UAT blocker fix — substation-centric workflow and data model correction

UAT found a critical workflow/data-model gap before acceptance: transformer creation exposed only
HV/LV switchyard pickers with no first-class substation context, so an engineer could not answer
"how many transformers are installed at substation X" or "which transformer belongs to X" without
indirectly inferring it from switchyard labels — and nothing prevented a transformer's HV and LV
switchyards from being selected at two different substations. **Malaysian transmission/distribution
domain rule, stated explicitly during UAT: a transformer is installed within a single substation and
is never modeled as equipment connected between two different substations.** See
[ADR-008](docs/adr/ADR-008-substation-voltage-yard.md)'s "Transformer Registry — UAT Correction"
addendum for the full architecture record.

**Backend.** `Transformer.substation_id` added as a mandatory column (previously substation context
was only reachable indirectly via each terminal's own `SubstationVoltageYard`). Both HV and LV
terminals must now resolve to this same `substation_id` — enforced at the service layer on creation,
checked before the same-switchyard/voltage-order checks so a cross-substation mismatch names the
specific offending side and both substation mnemonics
(`TransformerYardSubstationMismatchError`). Uniqueness moved from
`UNIQUE (hv_switchyard_id, lv_switchyard_id, transformer_number)` (service-layer-only, cross-row) to
**`UNIQUE(substation_id, transformer_number)`, a real single-table database constraint** — simpler
and stronger now that identity no longer spans two child rows. `TransformerSummary`/`TransformerDetail`
now carry `substation_id`/`substation_mnemonic`/`substation_official_name` directly (replacing the
former `hv_substation_mnemonic`/`lv_substation_mnemonic` pair, which is redundant once both terminals
are guaranteed to share one substation). `GET /api/v1/transformers` gained a `substation_id` filter.
Migration `0008_transformer_registry` was edited in place (never committed to version control before
this fix, so no new migration was needed) and re-verified end-to-end against the real dev PostgreSQL
database (drop-and-reapply, schema inspection confirming the new column, FK, and unique constraint).

**Frontend.** `TransformerCreatePage` is now substation-first: the user selects the substation before
either switchyard, and both HV/LV switchyard dropdowns are filtered client-side to that substation's
own switchyards only (mirroring `CircuitCreatePage`'s existing per-voltage-level filtering pattern) —
selecting a different substation clears any already-chosen switchyard. `TransformerListPage` shows a
"Substation" column (replacing the former HV/LV-substation "Switchyards" column) and the existing
free-text search already matches substation mnemonic/name. `TransformerDetailPage`'s heading and a new
"Substation" field show the parent substation explicitly. `SubstationDetailPage` gained a
"Transformers" section (reusing the new `substation_id` filter) so "which transformers are installed
here" is answered directly from a substation's own detail page — the specific UAT-reported
requirement.

**Tests.** Backend: 47 transformer tests total (31 service + 16 API; net +5 over the original 42) —
new coverage for cross-substation rejection on both HV and LV sides, substation-scoped uniqueness
allowing the same transformer number at a different substation, substation-id list/API filtering, and
substation fields present on every create/read response; one now-unreachable "equal voltage level via
two distinct same-substation switchyards" service test removed, since a substation can hold at most
one switchyard per voltage level once both switchyards must share a substation. 238 backend tests
total, passing against both SQLite and real PostgreSQL. Frontend: `TransformerCreatePage` tests
extended to cover substation-first selection, switchyard filtering by substation, and switchyard
reset on substation change; `TransformerListPage`/`TransformerDetailPage` tests updated for the new
substation fields; `SubstationDetailPage` gained 2 new tests for the "Transformers" section. 84
frontend tests total, passing; lint/typecheck/build all clean.

### Phase 3 follow-up — Engineering Connectivity section (Substation Detail page)

UAT clarified an architectural distinction the Transformer Registry work above surfaced but did not
itself resolve: **Transformer Registry answers asset ownership** ("which transformers are installed
at this substation"), while **Circuit Registry answers engineering connectivity** ("which circuits
are connected to this substation"). Unlike `Transformer`, `Circuit` does **not** gain a
`substation_id` column — a circuit legitimately connects two or more substations via its
`CircuitTerminal` rows, so it remains modeled exactly as it already was (§7.4–§7.5). See
`docs/architecture/equipment-registry-module.md`'s new "Engineering Connectivity" note for the full
architecture record, including the explicit distinction from PSS/E's future operational topology
snapshot.

**Backend.** `GET /api/v1/circuits` gained a `substation_id` filter (mirroring the equivalent filter
already added to `GET /api/v1/transformers`) — a circuit matches if any of its `CircuitTerminal` rows'
`SubstationVoltageYard.substation_id` equals the given substation, expressed as a read-only SQL join
across `Circuit`/`CircuitTerminal`/`SubstationVoltageYard` (CLAUDE.md F6 — permitted for query
optimisation/reporting; no data duplicated, no new table). No circular service dependency was
introduced — this stays inside Equipment Registry's own repository, reading `Substation` read-only
exactly as the existing `search` filter already does.

**Frontend.** `SubstationDetailPage` gained an "Engineering Connectivity" section (that exact
heading — not "Live Topology" or "Operational Connectivity", to keep this manually-maintained
engineering baseline visually and terminologically distinct from any future PSS/E-derived
operational snapshot) showing: a connected-circuits count, and a table with circuit name, bay number,
voltage level, line type, operational status, other connected terminal substations (derived from the
existing computed `circuit_name`, which already lists every terminal's substation mnemonic — no new
backend field needed), and a link to each circuit's detail page. Empty state:
"No connected circuits recorded in the engineering registry." Existing substation details, the
Switchyards section, and the Transformers section are unaffected; permission gating for the
edit/status-change forms is unchanged (this new section is read-only for every user, gated on nothing
beyond authentication, mirroring the Switchyards/Transformers sections' own read visibility).

**Tests.** Backend: 3 new service tests (`TestSubstationConnectivityFilter` — a circuit appears for
each of its own terminal substations, an unrelated substation sees nothing, the filter combines with
existing filters) plus 1 new API test (substation-id filter end-to-end, including a third, genuinely
unrelated substation created specifically to prove it sees nothing). 242 backend tests total, passing
against both SQLite and real PostgreSQL — live-verified via `curl` against the real dev database
(PKLG correctly returned its 2 real connected circuits; an unrelated substation returned zero).
Frontend: 2 new `SubstationDetailPage` tests (section renders with connected circuits and the correct
other-substation derivation; empty-state message shown when none exist). 86 frontend tests total,
passing; lint/typecheck/build all clean.

### Phase 3 follow-up — Deletion/Correction Policy

UAT found a practical gap this module's existing no-hard-delete rule (CLAUDE.md §11.6) had not yet
addressed: users could add switchyards, circuit terminals, and transformers by mistake, but had no
way to correct any of them. A new `ENTERED_IN_ERROR` operational status was added once to the shared
Core Platform `operational_status` reference table, distinct from `DECOMMISSIONED`/`RETIRED` (real
end-of-life) in that it represents a data-entry mistake. See
`docs/architecture/equipment-registry-module.md`'s new "Phase 3 Follow-up: Deletion/Correction
Policy" section for the full record, including the Architecture Decision Gate outcomes.

**Architecture Decision Gate.** Four questions were presented with a recommendation each before any
code was written: (1) `TransformerTerminal` correction is disallowed at the individual-terminal
level — a mistaken transformer is corrected only as a whole, since its HV/LV terminals are intrinsic
to what it is (exactly one of each, always); (2) `CircuitTerminal` correction is never blocked, even
when it would leave a circuit with fewer than two active terminals — a circuit may be temporarily
incomplete while under correction, but must satisfy the minimum two-active-terminal rule before it
can (re)enter an `Active` operational state, so the completeness check moved from correction-time to
activation-time; (3) default list views exclude entered-in-error records, revealed only via an
explicit opt-in query parameter; (4) `Circuit` and `Transformer` whole-entity correction reuse their
existing status-change paths — no new endpoint needed.

**Backend.** `SubstationVoltageYard.operational_status_id` and `CircuitTerminal.operational_status_id`
added as new, mandatory columns (previously neither entity had a status at all); `Circuit` and
`Transformer` simply gain a new legal value on their existing `operational_status_id` column;
`TransformerTerminal` deliberately gains no column. New `substation_voltage_yard_audit_log` table
closes a previously-documented gap (switchyard edits were only tracked via `updated_at`/
`updated_by_user_id`). A switchyard cannot be corrected to `ENTERED_IN_ERROR` while a non-entered-in-
error `CircuitTerminal` or `TransformerTerminal` still references it (on a non-entered-in-error
parent), and no new terminal can be created against a switchyard already `ENTERED_IN_ERROR`. New
`include_entered_in_error` query parameter (default `false`) on `GET /circuits`, `GET /transformers`,
`GET /voltage-yards`; detail endpoints remain unfiltered by status. New
`GET /api/v1/voltage-yards/{id}/audit-log` endpoint. Migration `0009_correction_status` — nullable
columns backfilled to `ACTIVE`, then `NOT NULL` + FK + index; new audit table; fully reversible.
Applied to the real dev database; schema and backfill verified via direct SQL (18/18 switchyards,
4/4 circuit terminals correctly backfilled to `ACTIVE`).

**Frontend.** "Mark as Entered in Error" action added to `SubstationDetailPage` (per switchyard) and
`CircuitDetailPage` (per terminal) — never "Delete", since this module has no concept of an
uncommitted draft. `SubstationDetailPage` always fetches switchyards with
`include_entered_in_error: true` (the database's `(substation_id, voltage_level_id)` uniqueness
constraint is not status-aware, so the "Add Switchyard" dropdown must always see corrected yards to
avoid re-offering an already-taken voltage level); a "Show entered-in-error switchyards" checkbox
filters the rendered list client-side only. `CircuitListPage` and `TransformerListPage` gained
equivalent "Show entered-in-error circuits/transformers" toggles wired to the new backend parameter.

**Tests.** Backend: 22 new tests (17 service + 5 API) covering switchyard/terminal correction,
reference-protection rejection, the activation guard, and default-list filtering. 264 backend tests
total, passing against both SQLite and real PostgreSQL. Frontend: 8 new tests across
`SubstationDetailPage`, `CircuitDetailPage`, `CircuitListPage`, and `TransformerListPage`. 94 frontend
tests total, passing; lint/typecheck/build all clean.

**Known limitations**

- `GET /api/v1/voltage-yards/{id}/audit-log` does not 404 on an unknown id — it returns an empty page,
  consistent with the existing behaviour of this module's other audit-log endpoints.
- No transition-legality graph is asserted for correcting a switchyard or circuit terminal to
  `ENTERED_IN_ERROR` beyond the reference-protection check itself — any active-status record may be
  corrected directly, mirroring `Transformer.operational_status_id`'s own unguarded status field.

### Phase 3.5 UAT fix #2 — transformer numbering model (uniqueness + breaker convention)

UAT found that `UNIQUE(substation_id, transformer_number)` (the Phase 3.5 UAT blocker fix above) was
itself too coarse: real Malaysian grid practice numbers transformer bays *per transformation pair*,
not per substation as a whole. A substation legitimately has a "Transformer Bay 1" on its 275/132kV
pair *and a separate* "Transformer Bay 1" on its 132/33kV pair — the substation-only constraint
wrongly rejected the second one. UAT separately found the breaker-number suggestion formulas
insufficient: they were keyed on voltage alone, but the correct formula depends on the transformation
pair and terminal side (e.g. 132kV needs `{N}10` as an HV side but `{N}80` as an LV side). See
[ADR-008](docs/adr/ADR-008-substation-voltage-yard.md)'s "UAT Correction #2 (Numbering Model)"
addendum for the full architecture record.

**Backend.** Uniqueness reverts to `(substation_id, hv_switchyard_id, lv_switchyard_id,
transformer_number)`, enforced at the service layer via an aliased double join on
`TransformerTerminal` (mirroring the module's original, pre-Phase-3.5-UAT-fix design) — not as a raw
database constraint, since denormalizing both switchyard ids onto `Transformer` to regain a
single-table constraint was considered and rejected (it would reintroduce the exact two-winding-only
assumption Decision 1 deliberately avoided baking into `Transformer`'s own column set, undermining
future tertiary-winding compatibility). Migration `0010_transformer_yard_pair` drops the now-incorrect
`uq_transformer_substation_number` constraint; no replacement single-table constraint is added.
`update_transformer` previously performed **no uniqueness check at all** when `transformer_number`
changed — a pre-existing gap, closed as part of this fix, since the exact same repository lookup now
backs both `create_transformer` and `update_transformer`. `DuplicateTransformerError`'s message was
reworded to name the HV/LV pair, not just the substation.

**Frontend.** `transformerBreakerSuggestion.ts` rewritten from a per-voltage table to a mapping keyed
by (HV nominal kV, LV nominal kV, side), covering the five transformation pairs the convention
specifies (500/275, 275/132, 132/33, 132/22, 132/11kV) — any other pair (e.g. one involving 230kV) has
no suggestion, an intentional scope limit. `TransformerCreatePage` now waits for both HV and LV
switchyards to be selected before suggesting either breaker number, since the formula genuinely
depends on the pair, not either voltage alone — a direct, accepted UX consequence of the corrected
model, not a regression.

**Tests.** Backend: 6 new tests (4 service + 2 API) covering same-number-different-pair allowance
(create and update), same-pair-same-number rejection (unchanged behaviour, re-verified against the new
implementation), and the previously-untested `update_transformer` uniqueness path. 271 backend tests
total (36 in `test_transformer_service.py`, 18 in `test_transformer_registry_api.py`), passing against
both SQLite and real PostgreSQL. Frontend: `transformerBreakerSuggestion.test.ts` rewritten (15 tests
covering all five transformation pairs, both sides, and the out-of-scope-pair/non-numeric-input null
cases); 2 `TransformerCreatePage` tests updated for the corrected LV-side formula and the
both-switchyards-required suggestion timing. 100 frontend tests total, passing; lint/typecheck/build
all clean.

### Transformer breaker-numbering convention moved to reference data

The (HV nominal kV, LV nominal kV, side)-keyed breaker-suggestion mapping introduced by the numbering-
model fix above was itself hardcoded in a frontend TypeScript file. Moved into a new Core Platform
reference table so the convention is auditable, seedable, and maintainable (a new transformation pair,
or a corrected pattern, is now a data change, not a frontend code change) without changing what the
convention actually says or its suggestion-only, never-backend-enforced nature.

**Backend.** New reference table `transformer_breaker_numbering_convention`
(`app/reference_data/models.py`) — `convention_id` (surrogate PK), `hv_voltage_level_id`/
`lv_voltage_level_id` (real FKs to `voltage_level`, not raw nominal-kV numbers), `side` (`CHECK IN
('HV','LV')`), `pattern` (nullable — `NULL` means no automatic suggestion), `is_standard`, `notes`.
`UNIQUE (hv_voltage_level_id, lv_voltage_level_id, side)`. No `created_at`/`updated_at` — consistent
with every other reference table in this module (`VoltageLevel`, `Region`, `State`, `GridOwner`,
`OperationalStatus`, `LineType`), none of which have them. Migration `0011_breaker_convention` creates
the table (no data — seeding is a separate step, per this project's established convention). Seeded
idempotently by `app/reference_data/seed.py`'s `run_seed`, with the exact ten rows (five transformation
pairs × two sides) matching the corrected convention exactly — safe to re-run, and backfills correctly
into a database seeded before this table existed (mirroring `line_type`'s own established backfill
guarantee). One real bug found and fixed along the way: this project's `SessionLocal` is configured
`autoflush=False` (`app/db/session.py`), so `run_seed` needed an explicit `db.flush()` after seeding
`voltage_level` and before seeding this new table, since it is the first seed function to depend on
another table's rows being visible within the same call — every prior seed function only ever queried
its own table. Exposed read-only via the existing reference-data router:
`GET /api/v1/reference-data/transformer-breaker-numbering-conventions` (authentication required, no
additional permission gate, matching every other reference-data endpoint). No write endpoint —
reference data is managed exclusively via the seed script, never through the API.

**Frontend.** `transformerBreakerSuggestion.ts` rewritten: the hardcoded pair/side lookup table is
gone, replaced by a pure function that takes the fetched convention list as a parameter and looks up
the matching row by `(hv_voltage_level_id, lv_voltage_level_id, side)`, applying `pattern`'s `{N}`
placeholder substitution. `TransformerCreatePage` now fetches the convention list via its own query and
gates suggestion display on four conditions: the transformer number, both switchyards' voltage levels,
and the convention list itself being loaded — a suggestion cannot appear until all four are ready. A
missing convention row, or a row with `pattern = null`, both correctly produce no suggestion, leaving
the breaker-number field free for manual entry — never a rejected or blocked input.

**Tests.** Backend: 3 new reference-data seed tests (exact seeded pattern/`is_standard` values matched
against the documented convention table; a dedicated backfill-into-a-partially-seeded-database test for
this table, mirroring `line_type`'s own) plus 2 new API tests (authentication required; every seeded
row returned, with the non-standard/null-pattern row distinguishable from a real pattern). 282 backend
tests total, passing against both SQLite and real PostgreSQL. Frontend: `transformerBreakerSuggestion.test.ts`
rewritten again for the new convention-array-based signature (16 tests, same coverage as before plus an
explicit "empty convention list" case); 1 new `TransformerCreatePage` test for the no-matching-convention/
manual-entry path. 102 frontend tests total, passing; lint/typecheck/build all clean.

### Phase 3.5 UAT fix #3 — ENTERED_IN_ERROR transformers permanently reserved their identity

UAT found that a transformer corrected to `ENTERED_IN_ERROR` still permanently occupied its
`(substation, HV switchyard, LV switchyard, transformer_number)` identity: creating "PKLG, 275kV HV,
132kV LV, Transformer 1" was rejected as a duplicate even though the only visible PKLG transformers
were both on the 132/11kV pair. The corrected record — hidden from every default view per the
deletion/correction policy — was still counted as "existing" by the uniqueness check, since
`find_transformer_by_yard_pair_and_number` never filtered on `operational_status_id`.

**Investigation (performed before any code change, at the user's explicit request).** Reconstructed
the exact submitted payload and queried `transformer`/`transformer_terminal` directly, confirming a
third PKLG transformer existed beyond the two visible ones: a stray `ENTERED_IN_ERROR` row from an
earlier live smoke test, sitting on exactly the 275kV/132kV pair with `transformer_number = "1"`. The
join/comparison logic in `find_transformer_by_yard_pair_and_number` was verified correct — real
switchyard ids, both terminals, no incorrect join — the sole gap was the missing status exclusion.
Frontend payload construction was also verified correct (switchyard ids submitted verbatim from the
selected options, no transformation).

**Backend.** `find_transformer_by_yard_pair_and_number` now excludes `ENTERED_IN_ERROR` transformers
(`Transformer.operational_status_id != _entered_in_error_status_id_subquery()`), mirroring the same
exclusion already used for switchyard reference-protection and default list filtering elsewhere in this
module. Applies automatically to both `create_transformer` and `update_transformer`, since both call
this same repository method. The corrected transformer row itself is never deleted or altered by this
fix — only excluded from this one uniqueness check — so it remains reachable by id and fully
audit-visible, consistent with CLAUDE.md §11.6 (no hard delete) and the deletion/correction policy's own
"hidden from default views, not from audit/history" principle.

**Tests.** Backend: 4 new service tests (`TestTransformerUniquenessExcludesEnteredInError` —
an `ENTERED_IN_ERROR` transformer no longer blocks recreating the same identity; an `ACTIVE`
transformer still correctly blocks a genuine duplicate; the same exclusion applies to
`update_transformer`) plus 1 new API test reproducing the full correction-then-recreation flow over
HTTP end-to-end, including confirming the corrected record remains reachable by `GET` afterward. 286
backend tests total, passing against both SQLite and real PostgreSQL. No frontend changes were
required — the bug was entirely in the backend uniqueness query. Live-verified via `curl` against the
real dev database: the exact reported scenario (PKLG, 275kV HV, 132kV LV, Transformer 1) now succeeds;
a subsequent genuine duplicate against the new record is still correctly rejected; the original stray
`ENTERED_IN_ERROR` artifact and this fix's own smoke-test transformer both remain reachable by id,
neither hard-deleted.

**Dev database cleanup.** The stray smoke-test artifact from an earlier session (`300aac73-...`,
PKLG, 275/132kV, "1") was left exactly as found — already correctly marked `ENTERED_IN_ERROR`, which is
itself the "neutralized" state this policy defines; hard-deleting it via raw SQL was deliberately not
done, since it would bypass this module's own audit/correction mechanism and CLAUDE.md §11.6 prohibits
hard delete on engineering entities regardless of whether a UI path exists for it. This fix's own new
smoke-test transformer was corrected to `ENTERED_IN_ERROR` the same way, for consistency.

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

### Phase 2 UAT fix — mnemonic uniqueness incorrectly rejected same-substation reuse

UAT found that renaming a substation's mnemonic away and then back (e.g.
`SIDS` → `SIDST` → `SIDS`) was incorrectly rejected with "Mnemonic ... is
already in use by a current or historical substation," even though the
historical alias being collided with belonged to the *same* substation
making the request. `_check_mnemonic_available`'s historical-alias check
(`repo.alias_mnemonic_exists_ci`) tested only whether any alias row existed
for the mnemonic, never *whose* alias it was — so a substation always
collided with its own retired mnemonics, and `exclude_substation_id` (already
threaded through correctly by both call sites) had no effect on this half of
the check.

**Backend.** `SubstationRepository.alias_mnemonic_exists_ci` (returned
`bool`) replaced with `find_alias_mnemonic_owner_ci` (returns the owning
`substation_id | None`), so the service can distinguish "this substation's
own historical mnemonic" (allow) from "a different substation's historical
mnemonic" (reject) — the same `exclude_substation_id` parameter used for the
live-record check now scopes the alias check too. Split the previously
single `DuplicateMnemonicError` into two distinct, more specific errors so a
user is never told the wrong reason: `DuplicateMnemonicError` ("already in
use by another *current* substation") and the new
`MnemonicReservedByHistoricalSubstationError` ("previously used by a
*different* substation ... permanently reserved to that substation's
identity"). `DuplicateNameError`'s message was updated to the same "another
current substation" phrasing for consistency; `official_name` was confirmed
to have no equivalent historical-reservation behavior to fix — unlike
mnemonic, substation-registry.md §8 rule 1 singles out mnemonic alone as
"a special, gated operation," and no code path ever writes
`SubstationAlias.alias_name`, so a name rename-and-back already worked
correctly before this fix and required no change.

**Tests.** 7 new tests: 4 in a new `TestMnemonicOwnershipAcrossRename` class
(same-substation reactivation of a historical mnemonic allowed; a different
substation's *current* mnemonic rejected; a different substation's
*historical* mnemonic rejected on both create and update), 1 documenting the
already-correct name rename-and-back behavior, and 2 new API tests
reproducing the exact UAT repro steps end-to-end over HTTP. The pre-existing
`test_retired_mnemonic_cannot_be_reassigned_to_a_new_substation` test was
updated to expect the new, more specific `MnemonicReservedByHistoricalSubstationError`.
271 backend tests total, passing against both SQLite and real PostgreSQL —
live-verified via `curl` against the real dev database reproducing the exact
`SIDS`-style rename-away-and-back sequence (succeeds) and a second
substation attempting to claim the first's retired mnemonic (rejected with
the new historical-reservation message).

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
