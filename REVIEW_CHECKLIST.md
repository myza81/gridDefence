# GridDefence Review Checklist

This checklist is used to review every implementation phase before it is
accepted as complete. It supplements — it does not replace — the Definition
of Done in [`.claude/CLAUDE.md`](.claude/CLAUDE.md) §25 and the per-phase
Definition of Done in
[`docs/architecture/implementation-plan.md`](docs/architecture/implementation-plan.md)
§12.

See [`DEVELOPMENT.md`](DEVELOPMENT.md) for the workflow this checklist
reviews the output of.

---

## 1. Standard Checklist — Every Phase

### Architecture compliance

- [ ] The module's architecture document under `docs/architecture/` exists,
      is current, and was followed exactly — no invented business rules.
- [ ] Any decision affecting domain ownership, versioning, security, or
      database standards is backed by an accepted ADR under `docs/adr/`.
- [ ] `docs/architecture/`, `docs/adr/`, and `.claude/` were not modified by
      the implementation session unless explicitly instructed.
- [ ] No architecture document was reinterpreted or redefined during
      implementation — conflicts were reported (`DEVELOPMENT.md` §9), not
      silently resolved.
- [ ] Only the requested phase was implemented — no functionality from a
      later phase was pulled forward.

### Backend layering

- [ ] Routers contain no business logic — each handler validates input,
      calls one service method, and shapes the response.
- [ ] All business rules and audit writes live in the service layer.
- [ ] Repositories contain no business logic — pure persistence access only.
- [ ] No module imports or writes to another module's repository or tables
      directly.
- [ ] No master data is duplicated across modules — referenced by foreign
      key or service call instead.
- [ ] No engineering value (threshold, priority, date, status) is
      hardcoded — it is read from the database or configured via
      environment variable, per `DEVELOPMENT.md` §7c.

### Database and migrations

- [ ] Every business entity uses a UUID primary key; every reference table
      uses a `SMALLINT`/`INTEGER` surrogate key (CLAUDE.md A5).
- [ ] Foreign keys enforce every relationship; no orphan records are
      possible.
- [ ] Cascading delete is not used on engineering entities
      (`ON DELETE RESTRICT` only).
- [ ] Each Alembic migration is a single logical schema change, has a
      working `downgrade()`, and was manually reviewed (not blindly
      committed from `--autogenerate`).
- [ ] No previously committed migration was modified — corrections are new
      migrations.
- [ ] Seed scripts are idempotent — re-running produces zero new rows.
- [ ] Any phase that adds or changes database schema has been verified
      against a real PostgreSQL database, not only SQLite (`DEVELOPMENT.md`
      §10 "PostgreSQL verification pass") — SQLite's flexible typing hides
      real constraint-enforcement differences (e.g. `SMALLINT` range).

### Security and audit

- [ ] Authentication is required for every non-public endpoint.
- [ ] Authorization checks fail closed — an unregistered permission,
      unknown user, or inactive user resolves to "denied," never "allowed."
- [ ] Every mutating action on an owned entity writes an audit record
      capturing who, when, what changed, and (where applicable) why.
- [ ] No secret, credential, or password hash is ever returned in an API
      response.
- [ ] No secret is committed to source control; defaults for
      security-sensitive settings are clearly non-production values.

### Testing

- [ ] Every business rule implemented has at least one corresponding
      automated test.
- [ ] Backend: `ruff check .` and `pytest` both pass.
- [ ] Frontend: `npm run lint`, `npm run typecheck`, `npm run test`, and
      `npm run build` all pass.
- [ ] Tests verify engineering/business outcomes, not implementation
      details.

### Reporting

- [ ] The implementation report follows the format in `DEVELOPMENT.md`
      §11 (all 11 sections present).
- [ ] Commands reported as run were actually run in the session, with
      real output — not paraphrased or assumed.
- [ ] Any environment limitation (no Docker, no reachable PostgreSQL,
      etc.) is stated explicitly, not silently omitted.

---

## 2. Phase-Specific High-Risk Review Targets

Beyond the standard checklist above, each phase introduces files that
carry outsized risk (security, identity, financial/engineering
correctness, irreversible data operations) and deserve a closer read than
the rest of the diff. This section is a running list, appended to by every
phase — never overwritten.

### Phase 1 — IAM + Core Reference Data

- **`backend/app/modules/iam/security.py`** — password hashing, access
  token issuance/verification, secret handling, expiry handling. Review
  for: passwords never stored or logged as plaintext; token signature
  verification uses constant-time comparison; expired or malformed tokens
  are rejected, never silently accepted; the signing secret is read from
  configuration, never hardcoded.
- **`backend/app/modules/iam/bootstrap.py`** — bootstrap Administrator
  creation. Review for: idempotency (safe to run against an
  already-bootstrapped database); the bootstrap account cannot be silently
  recreated or duplicated; every write during bootstrap is audited with a
  non-null actor.
- **`backend/app/core/config.py`** — `SECRET_KEY` and other
  security-relevant settings. Review for: no real secret is hardcoded as a
  default; every security-sensitive default is an obviously-non-production
  placeholder; all such values are overridable via environment variable
  and never require a source change to rotate.
- **`backend/app/modules/iam/router.py`** — authentication and
  authorization endpoints. Review for: every mutating/administrative route
  is gated by the correct permission dependency; no route bypasses
  `get_current_user`/`require_permission` where it should apply; no
  business logic leaked into the router itself.

### Phase 2 UAT fix — mnemonic uniqueness ownership across rename

- **`backend/app/modules/substation_registry/service.py`** —
  `_check_mnemonic_available`'s historical-alias check now compares the
  alias's *owning* `substation_id` against `exclude_substation_id`, not
  merely whether the mnemonic exists in `substation_alias` at all. Review
  for: any future change to this method must preserve the distinction
  between "this substation's own historical mnemonic" (allow) and "a
  different substation's historical mnemonic" (reject) — collapsing the
  check back to a bare existence test reintroduces the exact UAT bug this
  fix corrected (`SIDS` → `SIDST` → `SIDS` incorrectly rejected).
- **`backend/app/modules/substation_registry/repository.py`** —
  `find_alias_mnemonic_owner_ci` returns the owning `substation_id`, not a
  `bool`. Review for: any caller must compare the returned id against the
  substation making the request, not just check for `None` — treating a
  non-`None` return as "always reject" reintroduces the same bug in a new
  location.
- **`official_name` deliberately received no equivalent alias-reservation
  fix.** `SubstationAlias.alias_name` exists in the schema but no code path
  writes it — substation-registry.md §8 rule 1 treats mnemonic alone as
  requiring this "special, gated" historical-reservation treatment; name
  changes are an ordinary audited update. Review for: do not add
  historical-name reservation logic without an explicit architecture
  decision — the current asymmetry between mnemonic and name is
  intentional, not an oversight this fix missed.

### Phase 3 — Equipment Registry (Circuit / CircuitTerminal Management)

- **`backend/app/modules/equipment_registry/models.py`** — deviates from
  the full specification (`docs/architecture/equipment-registry-module.md`
  §7.1, §7.5) by giving `CircuitTerminal` its own identity
  (`circuit_terminal_id`) rather than sitting on a shared `Equipment`
  backbone, since no other equipment type (transformer, relay) is
  implemented yet. Review for: this scoping decision remains documented in
  the module docstring and this phase's implementation report, and is
  revisited (not silently perpetuated) once a second equipment type is
  actually added.
- **`backend/app/modules/equipment_registry/service.py`** — `create_circuit`
  is the only path that can bring a `Circuit` into existence, and does so
  together with its terminals in one transaction. Review for: the
  two-terminal minimum (`_validate_terminal_inputs`) and the
  duplicate-substation check are both enforced *before* any row is
  written, so a rejected creation never leaves a partially-formed circuit
  behind; `add_terminal` re-checks the same duplicate-substation rule
  independently for the extend-into-a-tee-off path.
- **`backend/app/modules/equipment_registry/repository.py`** — `list_circuits`'s
  `search` filter performs a read-only cross-module join against
  `Substation` (permitted under CLAUDE.md F6/DEVELOPMENT.md §7a for
  reporting only). Review for: no write path anywhere in this file touches
  `Substation`; the `_in_smallint_range` guard on `voltage_level_id`/
  `line_type_id`/`operational_status_id` filters (added after this phase's
  PostgreSQL verification pass caught a `NumericValueOutOfRange` on an
  out-of-range filter value — invisible under SQLite) is not accidentally
  removed by a future refactor.
- **`backend/alembic/versions/0004_equipment_registry_circuits.py`** —
  introduces `uq_circuit_terminal_substation` (business rule 6: no
  substation may hold more than one terminal of the same circuit) and
  `ON DELETE RESTRICT` on every foreign key. Review for: both constraints
  are present in the SQLAlchemy models *and* the migration, byte-for-byte
  consistent (DEVELOPMENT.md §8).
- **`backend/app/modules/equipment_registry/bootstrap.py` (deployment, not
  code correctness)** — found during Phase 3 UAT: this file is never
  invoked automatically (no startup hook in `main.py`, no lazy-bootstrap on
  login) and, before this UAT fix, was never documented as a required
  setup step outside the automated test suite's own fixtures. Running
  `alembic upgrade head` alone leaves every module's permissions
  unregistered and ungranted. Now documented in README.md's "Seeding and
  Bootstrapping" section. Review for: any future module's bootstrap step
  is added to that same README list the same PR/session it ships, not
  left to be discovered during UAT again.

### Phase 3 UAT fix package — SubstationVoltageYard, full circuit edit, terminal editability (ADR-008)

- **`backend/alembic/versions/0005_substation_voltage_yard.py`** — the
  first migration in this project that backfills real data from existing
  rows, not just schema (see README.md's "Seeding and Bootstrapping"
  section for how this differs from seed/bootstrap steps). Review for: the
  backfill creates exactly one `substation_voltage_yard` row per existing
  substation (using that substation's own `voltage_level_id`) before
  `circuit_terminal.voltage_yard_id` is populated and made `NOT NULL`; the
  old `substation_id` column and its FK/unique constraint/index are dropped
  only *after* the new column is fully backfilled — never dropped first;
  `downgrade()` correctly restores `substation_id` by joining back through
  `substation_voltage_yard`, verified directly against the real dev
  database's pre-existing rows (5 substations, 4 terminals), not only in
  the abstract.
- **`backend/app/modules/equipment_registry/models.py`** —
  `uq_circuit_terminal_voltage_yard` (business rule 6, restated at
  voltage-yard granularity per ADR-008) deliberately does **not** restate
  the rule at substation granularity — a circuit terminating twice at the
  same multi-voltage substation, once per voltage yard, must remain legal.
  Review for: no future change silently reintroduces a substation-level
  uniqueness constraint here, which would make that scenario impossible to
  express again.
- **`backend/app/modules/equipment_registry/service.py`** —
  `create_voltage_yard` enforces at most one yard per
  `(substation_id, voltage_level_id)` pair; `update_terminal` is the new
  write path for `breaker_number`/`commissioning_date`/`remarks` after
  creation (Phase 3 UAT must-fix items 1–2) and does not allow
  `voltage_yard_id` itself to be changed (deliberately out of this fix
  package's scope — re-pointing a terminal to a different yard is a
  materially different operation). Review for: `update_terminal` verifies
  the terminal actually belongs to the given `circuit_id` before mutating
  it (a terminal ID alone is not sufficient authorization context).
- **Frontend/backend error-message parity (found during Phase 3 UAT
  validation)** — `DuplicateVoltageYardError` originally embedded raw
  UUIDs/internal ids in its message; a UAT tester hit this on the very
  first natural use of the add-voltage-yard form, since the dropdown
  didn't yet filter out already-used voltage levels. The automated test
  covering this workflow passed anyway, because its own mock data
  coincidentally exercised the exact duplicate case and the mock POST
  handler didn't enforce the real constraint. Review for: any future
  business exception message is checked against what a human would
  actually see and understand, not just that *an* error is raised; any
  test asserting a "successful" write against mocked data is checked for
  whether that same input would actually succeed against the real backend
  the mock stands in for.

### Phase 3 UAT follow-up — `Substation.voltage_level_id` deprecation (ADR-009)

- **`backend/alembic/versions/0006_deprecate_substation_vlevel.py`** —
  relaxes a `NOT NULL` constraint only; no data is touched or backfilled.
  Review for: the revision id is deliberately abbreviated ("vlevel") to fit
  `alembic_version.version_num`'s `VARCHAR(32)` limit — a mistake caught
  during this phase's own PostgreSQL verification pass (the first migration
  attempt failed on `StringDataRightTruncation` writing the version stamp,
  not on the schema change itself; transactional DDL correctly rolled the
  whole migration back). Any future migration's revision id must be checked
  against this same 32-character limit before being written to the dev
  database.
- **`backend/app/modules/substation_registry/service.py`,
  `schemas.py`, `router.py`, `repository.py`** — `voltage_level_id` is
  removed from the entire Create/Update/List-filter/Summary/Detail surface,
  not just hidden in the UI. Review for: no remaining code path in this
  module reads, writes, or validates `Substation.voltage_level_id` — the
  only reference left is the deprecation comment on the model column
  itself; a future PR must not quietly reintroduce it as a convenience
  default without a new ADR, since ADR-009 specifically rejected
  auto-creating a matching voltage yard on Substation Create as
  re-introducing the single-voltage assumption this phase removed.
- **Dependency direction (CLAUDE.md A2/F2)** — `SubstationListPage.tsx`
  composes each substation's voltage yards by calling Equipment Registry's
  `GET /api/v1/voltage-yards` directly from the frontend and grouping
  client-side, specifically to avoid a backend join from Substation
  Registry (Master Data) into Equipment Registry (Network Data), which
  CLAUDE.md forbids. Review for: no future "convenience" refactor moves
  this join into Substation Registry's own repository/service layer — the
  join must stay client-side, or move to a genuinely separate
  reporting/dashboard read model (CLAUDE.md F6), never into Substation
  Registry's own primary List/Detail read path.
- **ADR immutability** — ADR-009 revisits a specific claim made in
  ADR-008's Decision section ("substation-registry.md unaffected in
  ownership"). Review for: ADR-008's own decision text was not rewritten —
  only a short pointer note was prepended, consistent with this project's
  practice of treating ADRs as an append-only historical record even when
  a later ADR narrows an earlier one's scope.

### Phase 3 UAT follow-up — inline voltage yard creation removed from Circuit Detail (ADR-009 addendum)

- **`frontend/src/modules/equipment_registry/pages/CircuitDetailPage.tsx`** —
  no longer imports `substationRegistryApi` or calls
  `equipmentRegistryApi.createVoltageYard`; this page must only ever call
  `GET /api/v1/voltage-yards` (read), never `POST`. Review for: any future
  PR touching this file that reintroduces a `POST /voltage-yards` call, a
  substation-select dropdown, or any other master-data creation control is
  a direct violation of the ADR-009 addendum's principle and must be
  rejected without a new ADR explicitly justifying the exception.
- **General principle (ADR-009 addendum)** — "master data entities are
  created and managed only within their owning module." Review for: every
  future topology entity (Busbar, Bus Coupler, Transformer, Disconnector,
  Reactor, Capacitor, and PSS/E-imported equipment) gets its creation
  workflow built exactly once, in its owning module's own page — never
  duplicated as a convenience shortcut inside a page that only consumes it.
  A page needing an entity that doesn't exist yet shows guidance text
  pointing to the owning module, not an inline form.

### Phase 3 close-out — terminal voltage-level guardrail and voltage yard metadata

- **`backend/app/modules/equipment_registry/service.py`** —
  `_require_voltage_yard_matches_circuit_level` is called from both
  `create_circuit` (via `_validate_terminal_inputs`) and `add_terminal`.
  Review for: `create_circuit` validates `voltage_level_id`/`line_type_id`
  as real reference data *before* calling `_validate_terminal_inputs` —
  the ordering matters, since the mismatch-error label resolution needs a
  real `circuit_voltage_level_id` to look up; a future refactor that
  reorders these two calls would silently degrade the error message to a
  raw id fallback instead of failing the way `ReferenceDataNotFoundError`
  already would.
- **`backend/alembic/versions/0007_voltage_yard_metadata.py`** — adds
  three nullable columns plus CHECK constraints and a backfilled
  `updated_at`/`updated_by_user_id` pair, no metadata backfill. Review
  for: the three metadata columns are genuinely nullable with no
  backfill (correct — every pre-existing row must remain valid with
  `NULL`s per the task's explicit requirement), while
  `updated_at`/`updated_by_user_id` ARE backfilled from
  `created_at`/`created_by_user_id` before being made `NOT NULL` (correct
  — mirrors `0005_substation_voltage_yard.py`'s identical pattern for
  `circuit_terminal`).
- **Known audit gap (accepted trade-off, not an oversight)** —
  `update_voltage_yard` records `updated_at`/`updated_by_user_id` but
  does **not** write to a field-level audit log (unlike every other
  mutable entity in this codebase — `SubstationAuditLog`,
  `EquipmentRegistryAuditLog`). Judged proportionate for this
  incremental metadata addition rather than building an unrequested
  `substation_voltage_yard_audit_log` table plus its own read endpoint
  and UI. Review for: if voltage yard metadata becomes
  compliance-relevant (e.g. referenced by PSS/E import provenance or an
  audit requirement surfaces from real UAT), add the missing audit log
  table before that dependency lands — do not silently let this gap
  become permanent by omission.
- **ADR-008 addendum (rule 6a reconciliation)** — the addendum records
  that a circuit can no longer terminate twice at the same substation
  under the current model, once rule 6a is combined with the existing
  one-yard-per-substation-per-level constraint. Review for: when a
  `Transformer` equipment type is eventually introduced (this ADR's
  addendum explicitly anticipates it), confirm whether that scenario
  should be revisited via a new ADR rather than silently reusing
  `Circuit`/`CircuitTerminal` for a fundamentally different equipment
  type.

### Phase 3 freeze package — bay number semantics, canonical naming, Switchyard terminology

- **`backend/app/modules/equipment_registry/service.py`** —
  `_compute_circuit_name` no longer takes `bay_number` and now sorts
  mnemonics (`sorted(mnemonics, key=str.casefold)`) instead of using
  terminal-insertion order. Review for: both call sites
  (`get_circuit`, `list_circuits`) were updated together — a future
  change to either read path that reintroduces bay_number concatenation
  or drops the sort would silently reintroduce both UAT-found defects
  (duplicated-looking display, non-deterministic naming) at once, since
  they share one root cause and one fix.
- **Found-and-fixed pre-existing false positive** — before this fix,
  `CircuitListPage.test.tsx`'s only test literally reconstructed the bug
  UAT reported (`circuit_name: "PKLG–IGBK Line 1"` shown next to a
  separate `bay_number: "Line 1"` cell) and still passed, because the
  test was asserting against static mock data, not exercising the naming
  logic itself. Review for: any test using a hardcoded `circuit_name`
  mock should reflect the *current* computation rule (sorted mnemonics,
  no bay_number), not an arbitrary plausible-looking string — a mock
  that outlives the logic it was modeling is a recurring failure mode in
  this codebase (see also the Phase 3 UAT validation fix's own
  "Frontend/backend error-message parity" lesson above).
- **Terminology relabeling (ADR-008 addendum, Option B)** — UI text and
  user-facing error messages now say "Switchyard"; internal
  model/table/column/API names (`SubstationVoltageYard`,
  `substation_voltage_yard`, `voltage_yard_id`, `/api/v1/voltage-yards`)
  are unchanged. Review for: any *new* code added after this point
  should follow the same split deliberately — new user-facing text says
  "Switchyard," new internal identifiers may continue to say
  "voltage_yard" for consistency with existing code, and a PR should not
  "helpfully" rename one without the other without revisiting the ADR-008
  addendum's reasoning first.
- **Architecture document direct-edit practice** — `bay_number`'s
  `equipment-registry-module.md` examples were corrected directly in
  §7.4/§7.6 (not left stale with only a pointer note), while the longer
  narrative walkthroughs in §7.9/§7.11/§7.13 were left as originally
  written, with one disambiguating note added near the top instead of an
  exhaustive rewrite. Review for: if a future phase touches those
  walkthrough sections for an unrelated reason, update their "Line 1"-
  style examples to the current convention as a low-cost side effect,
  rather than perpetuating the split indefinitely.

### Phase 3.5 — Transformer Registry

- **UAT blocker fix (substation ownership) — read this before reviewing anything else in this
  section.** The original Phase 3.5 design (bullets below, as originally written) allowed a
  transformer's HV and LV switchyards to belong to two different substations, and exposed no
  first-class substation context anywhere. UAT correctly rejected this: in the Malaysian
  transmission/distribution domain, a transformer is substation-owned equipment, never modeled as
  spanning two substations. Fixed by adding `Transformer.substation_id` (mandatory), requiring both
  terminals to belong to it (`EquipmentRegistryService._require_yard_belongs_to_substation`,
  raising `TransformerYardSubstationMismatchError` on mismatch), and moving uniqueness to a real
  `UNIQUE(substation_id, transformer_number)` database constraint. See
  [ADR-008](docs/adr/ADR-008-substation-voltage-yard.md)'s "UAT Correction" addendum for the full
  record. The bullets below describe the *current, corrected* state, not the original design.
- **`backend/app/modules/equipment_registry/repository.py`** — **superseded by UAT fix #2, see the
  dedicated subsection below.** `find_transformer_by_substation_and_number` (a bare `(substation_id,
  transformer_number)` lookup backed by a real database `UNIQUE` constraint) no longer exists — it was
  replaced by `find_transformer_by_yard_pair_and_number`, a service-layer-only check spanning the
  HV/LV switchyard pair too. Do not reintroduce the single-table constraint this bullet used to
  describe; see below for why.
- **`backend/app/modules/equipment_registry/service.py`** —
  `_compute_transformer_short_name` and
  `_TRANSFORMER_SHORT_NAME_PREFIX_BY_NOMINAL_KV` are the sole source of
  the generated short name; it is computed on every read (`get_transformer`,
  `list_transformers`), never stored. Review for: a future edit that adds
  a `generated_short_name` column to persist this value would reopen the
  exact drift risk this phase's Architecture Decision Gate rejected
  (Decision 2) — the computed-at-read-time approach must be preserved
  unless a new ADR revisits it.
- **`backend/app/modules/equipment_registry/models.py`** — `Transformer`
  and `TransformerTerminal` are new, independent entities (own PKs, own
  audit log), not attached to the shared `Equipment` backbone described in
  §7.1 of the architecture doc — same deliberate scoping choice already
  applied to `Circuit`/`CircuitTerminal` in Phase 3, extended consistently
  rather than reopened. `TransformerTerminal.side` is a
  CHECK-constrained string (`'HV'`/`'LV'`), not an enum type or reference
  table — chosen specifically so a future tertiary-winding phase can add a
  third `side` value via a constraint change alone. `Transformer.substation_id`
  (UAT correction) is a plain FK to `substation`, `ON DELETE RESTRICT` —
  there is no database-level constraint forcing both `TransformerTerminal`
  rows' switchyards to belong to this same substation (a cross-table
  equality check spanning three tables is not expressible as a
  single-table constraint), so that invariant depends entirely on
  `create_transformer` being the only write path. Review for: this scoping
  decision remains documented (module docstring, this phase's
  implementation report, and the ADR-008 addendum) and is revisited when
  tertiary windings are actually implemented, not silently perpetuated;
  any future direct-write path to `TransformerTerminal` must re-implement
  the substation-membership check or the invariant silently breaks.
- **`frontend/src/modules/equipment_registry/transformerBreakerSuggestion.ts`** —
  a pure, frontend-only function; the backend never validates or enforces
  breaker-number format (per the spec: "backend must NEVER reject a
  custom breaker number"). Review for: no future change should add
  backend-side format validation for `breaker_number` without an explicit
  new requirement, since doing so would silently break the "always
  overridable" guarantee this phase was built around.
- **`backend/alembic/versions/0008_transformer_registry.py`** — no data
  backfill (new tables, no pre-existing rows) — simpler than
  `0005_substation_voltage_yard`'s backfill migration, but still manually
  reviewed and verified against real PostgreSQL (schema inspection of all
  three new tables) rather than assumed correct from the model definitions
  alone. Review for: `ON DELETE RESTRICT` on every foreign key and the
  `ck_transformer_terminal_side`/`uq_transformer_terminal_side`/
  `uq_transformer_substation_number` constraints are present in both the
  SQLAlchemy models and the migration, byte-for-byte consistent
  (DEVELOPMENT.md §8). This migration was edited in place for the UAT
  correction (never committed to version control beforehand — see
  DEVELOPMENT.md's migration rules on when in-place edits are permitted);
  it was downgraded/re-upgraded against the real dev database rather than
  assumed safe, since the table had already been created once under the
  original schema.
- **No manual browser UAT was performed** — no browser automation tool was
  available in the implementation environment; the workflow/data-model UAT
  finding that produced this section's own fix was reported directly by
  the user, not caught by this phase's own automated tests, which is
  exactly the class of gap functional review catches that RTL/API tests
  do not (neither kind of test can notice that a *legal-per-the-schema*
  cross-substation transformer is operationally nonsensical, only a human
  reviewing the actual workflow against real domain rules can). Review
  for: before this phase is frozen/tagged, a human should still exercise
  the corrected Transformer Create/List/Detail workflow, and the new
  Substation Detail "Transformers" section, in a real browser against a
  real backend at least once, the same gate every prior phase's UAT step
  applied.

### Phase 3.5 UAT fix #2 — transformer numbering model (uniqueness + breaker convention)

- **Do not re-add a single-table `UNIQUE` constraint on `transformer` for transformer-number
  uniqueness, and do not denormalize `hv_switchyard_id`/`lv_switchyard_id` onto `Transformer` to make
  one possible.** Both were tried, in sequence, and both were wrong: the substation-only key
  (`UNIQUE(substation_id, transformer_number)`, the Phase 3.5 UAT blocker fix above) incorrectly
  rejected the same bay number on two different transformation pairs at one substation — real
  Malaysian grid practice numbers bays per pair, not per substation. Denormalizing the two switchyard
  ids onto `Transformer` to regain a single-table constraint was considered next and rejected, because
  it would reintroduce the exact two-winding-only assumption Decision 1 (ADR-008 addendum) deliberately
  kept out of `Transformer`'s own column set — a future tertiary-winding phase would need a third
  denormalized column, breaking Decision 1's "zero migration to `Transformer` itself" guarantee.
  Uniqueness is enforced at the service layer only, scoped to `(substation_id, hv_switchyard_id,
  lv_switchyard_id, transformer_number)`, via `EquipmentRegistryRepository.find_transformer_by_yard_pair_and_number`
  (an aliased double join on `TransformerTerminal`). Review for: any future PR proposing to "simplify"
  this back to a database constraint should be rejected unless it also revisits Decision 1 via a new ADR.
- **`backend/app/modules/equipment_registry/service.py`** — `update_transformer` previously performed
  **no uniqueness check whatsoever** when `transformer_number` changed — a pre-existing gap (not
  introduced by this fix) that would have let a `PATCH` silently create a duplicate identity, either
  under the old or the new uniqueness scope. Closed by calling the same
  `find_transformer_by_yard_pair_and_number` lookup used by `create_transformer`, using the
  transformer's own existing (immutable, per Business Rule 6) HV/LV terminal switchyard ids and
  `exclude_transformer_id=transformer_id` so a transformer never collides with itself. Review for: any
  future field added to `update_transformer` that can affect identity uniqueness must get its own
  explicit re-check — this class of gap (an update path silently skipping a check its own create path
  enforces) is exactly what went unnoticed here until UAT found it.
- **`frontend/src/modules/equipment_registry/transformerBreakerSuggestion.ts`** — rewritten from a
  per-voltage table to a mapping keyed by (HV nominal kV, LV nominal kV, side); only the five
  transformation pairs the convention specifies have an entry. Review for: do not add a formula for an
  unspecified pair (e.g. one involving 230kV) by inferring or interpolating one — CLAUDE.md ("Claude
  must not invent business rules") applies to display-only suggestions too, not just backend
  validation; a missing suggestion (user types the breaker number manually) is the correct behaviour
  for an out-of-scope pair, not a bug to "fix" by guessing.
- **`frontend/src/modules/equipment_registry/pages/TransformerCreatePage.tsx`** — a breaker-number
  suggestion for either side now only appears once **both** HV and LV switchyards are selected (the
  formula genuinely depends on the pair). Review for: this is an accepted, direct consequence of the
  corrected model, not a regression to "fix" by reintroducing a per-side-only suggestion — doing so
  would silently resurrect the exact wrong-formula bug this fix corrected.

### Transformer breaker-numbering convention moved to reference data

- **Do not reintroduce a hardcoded pair/side lookup table in
  `frontend/src/modules/equipment_registry/transformerBreakerSuggestion.ts`.** The whole point of this
  change was to make the convention a data change (`app/reference_data/seed.py`), not a frontend code
  change. Review for: any future PR that adds a new transformation pair or corrects a pattern by
  editing this `.ts` file directly, rather than the seed data, should be rejected — it silently
  reintroduces the exact hardcoding this correction removed.
- **`backend/app/reference_data/seed.py`** — `_seed_transformer_breaker_numbering_conventions` depends
  on `voltage_level` rows added earlier in the *same* `run_seed` call being visible to its own query,
  which required adding an explicit `db.flush()` between the two seed calls — this project's
  `SessionLocal` is `autoflush=False` (`app/db/session.py`), so this cannot be left implicit. Review
  for: any future reference table whose seed function queries a *different* table populated earlier in
  the same `run_seed` call needs the same explicit flush (or must be ordered after an existing one) —
  every seed function before this one only ever queried its own table, so this dependency is new and
  easy to miss by copying an existing seed function as a template without noticing the difference.
- **`backend/app/reference_data/models.py`** — `TransformerBreakerNumberingConvention` deliberately has
  no `created_at`/`updated_at` columns, for consistency with every other reference table in this module.
  Review for: do not add them here alone as a "nice to have" — if audit history for reference-data
  changes is ever needed, it should be designed once for every reference table (a new ADR), not
  introduced piecemeal on whichever table happened to be touched most recently.
- **This remains suggestion-only, not backend validation** — moving the convention to the database
  changed *where the suggestion comes from*, not *whether it is enforced*. Review for: any future PR
  that adds backend-side format validation for `TransformerTerminal.breaker_number` against this
  convention table should be rejected without an explicit new requirement — Business Rule 7
  (equipment-registry-module.md) states this convention is a display-only convenience, unchanged by
  this correction.
- **No manual browser UAT was performed** for this change, for the same environment reason as prior
  phases. Review for: exercise `TransformerCreatePage`'s breaker-number suggestions in a real browser
  against the real seeded reference data before this phase is frozen/tagged.

### Phase 3.5 UAT fix #3 — ENTERED_IN_ERROR transformers permanently reserved their identity

- **`backend/app/modules/equipment_registry/repository.py`** —
  `find_transformer_by_yard_pair_and_number` now excludes `Transformer.operational_status_id ==
  ENTERED_IN_ERROR` from its uniqueness check. Review for: any future uniqueness or reference-lookup
  query added to this module that reads `Transformer`, `Circuit`, `SubstationVoltageYard`, or
  `CircuitTerminal` rows must apply the same exclusion unless there is a specific, documented reason
  not to — the deletion/correction policy's whole premise is that a corrected record is "not a real
  engineering asset," and a query that silently treats it as one reintroduces exactly this bug in a new
  location. Grep for `_entered_in_error_status_id_subquery()` usage sites as a checklist before adding
  a new query against any entity this policy covers.
- **This was found by the user reproducing a real workflow, not by this module's own automated tests.**
  Every existing uniqueness test used only `ACTIVE` transformers, so none of them could have caught a
  bug that only manifests once a corrected record exists. Review for: when adding tests for any new
  uniqueness/reference rule in this module going forward, include at least one case with an
  `ENTERED_IN_ERROR` row present, not only `ACTIVE` rows — this class of gap is easy to miss precisely
  because it requires a specific prior history (a mistake, then a correction) to surface.
- **The corrected transformer row is never deleted by this fix** — only excluded from the uniqueness
  check. Review for: do not "simplify" this into an actual row deletion or a data-migration cleanup
  script; CLAUDE.md §11.6 prohibits hard delete on engineering entities, and this module has no
  `DELETE` endpoint for exactly that reason.
- **Dev database cleanup performed via the application's own status-correction endpoint, not raw
  SQL.** The stray smoke-test artifact (`300aac73-...`) was left as `ENTERED_IN_ERROR` (already the
  correct, neutralized state) rather than hard-deleted. Review for: any future dev-database cleanup in
  this module should use `PATCH .../transformers/{id}` (or the equivalent status-correction path for
  other entities), never a direct `DELETE FROM` against a live database — even for disposable
  smoke-test data — since it bypasses audit logging and risks violating FK constraints from rows this
  session cannot see.

### Phase 3 follow-up — Engineering Connectivity (Substation Detail page)

- **Do not repeat the Transformer Registry's original mistake here.** `Circuit` must **not** gain a
  `substation_id` column — a circuit legitimately connects two or more substations via
  `CircuitTerminal`, unlike a transformer, which is substation-owned equipment (the distinction UAT
  itself drew explicitly). Review for: any future PR that proposes `Circuit.substation_id` "for
  consistency with Transformer" should be rejected; the asymmetry between the two entities is
  intentional and documented (equipment-registry-module.md's Engineering Connectivity note).
- **`backend/app/modules/equipment_registry/repository.py`** — `list_circuits`'s new
  `substation_id` filter is a read-only subquery through
  `CircuitTerminal` → `SubstationVoltageYard`, structurally identical to the pattern already used by
  `list_circuits`'s own `search` filter and by `list_transformers`'s `substation_id` filter. Review
  for: no write path was added alongside it, and no new table/column was introduced — this filter
  derives its answer entirely from data Equipment Registry already owns (CLAUDE.md §5.1 — no
  duplication).
- **`frontend/src/modules/substation_registry/pages/SubstationDetailPage.tsx`** — "Other Connected
  Substations" is derived by parsing the existing computed `circuit_name` (splitting on the en dash
  `"–"` the backend's own `_compute_circuit_name` joins with) rather than adding a new backend field.
  Review for: if `_compute_circuit_name`'s separator or sorting convention ever changes, this
  frontend parsing logic must change with it — the two are coupled by convention, not by a shared
  constant, since the frontend has no authoritative source for the separator character other than
  matching the backend's current implementation.
- **Naming discipline.** The section is titled exactly "Engineering Connectivity," deliberately not
  "Live Topology" or "Operational Connectivity" — those names are reserved for the future,
  PSS/E-derived operational snapshot (Phase 4). Review for: any future PSS/E connectivity UI must use
  different, clearly operational-sounding terminology, and must never silently merge with or
  overwrite this section — the architecture note in equipment-registry-module.md states GridDefence
  should compare the two, never let one silently supersede the other.
- **No manual browser UAT was performed** for this follow-up either, for the same environment reason
  as above. Review for: exercise the new "Engineering Connectivity" section in a real browser
  alongside the Transformer Create/List/Detail workflow before this phase is frozen/tagged.

### Phase 3 follow-up — Deletion/Correction Policy

- **Do not add a status column to `TransformerTerminal`.** This was a deliberate Architecture
  Decision Gate outcome (Q1), not an oversight: a transformer's HV and LV terminals are intrinsic to
  what it is (exactly one of each, always), so a single mistaken terminal cannot be corrected in
  isolation without leaving an invalid transformer on record. Review for: any future PR that adds
  `TransformerTerminal.operational_status_id` "for consistency with `CircuitTerminal`" should be
  rejected — the correction unit for a mistaken transformer is the whole `Transformer`, via its own
  pre-existing `operational_status_id` field.
- **Do not block `CircuitTerminal` correction, even below the two-active-terminal minimum.** This was
  explicit, detailed user guidance (Q2), not a relaxed default: `CircuitTerminal` is a first-class
  connectivity object that may legitimately require individual correction, and a circuit may be
  temporarily incomplete while under correction. The two-active-terminal rule (equipment-
  registry-module.md §9 rule 5) is enforced only at the point a circuit tries to (re)enter `Active`
  (`change_status`), never at terminal-correction time. Review for: any future PR that adds a guard
  to `update_terminal` preventing correction below the threshold should be rejected — it would
  contradict this explicit decision and reintroduce the exact rigidity UAT flagged.
- **`backend/app/modules/equipment_registry/service.py`** — `_require_voltage_yard` now raises
  `SwitchyardEnteredInErrorError` for any yard whose status is `ENTERED_IN_ERROR`, which is what
  actually protects every terminal-creation call site (`_validate_terminal_inputs`, `add_terminal`,
  `create_transformer`) — there is no separate guard duplicated at each call site. Review for: any
  new terminal-creation path added in a future phase must route through `_require_voltage_yard` (or
  an equivalent check) rather than fetching the yard directly, or it will silently bypass this
  protection.
- **`backend/app/modules/equipment_registry/repository.py`** — `list_circuits`/`list_transformers`/
  `list_voltage_yards`'s default `ENTERED_IN_ERROR` exclusion is bypassed whenever an explicit
  `operational_status_id` filter is supplied (`if not include_entered_in_error and
  operational_status_id is None`). Review for: this is intentional — without it, directly filtering
  for `?operational_status_id=<entered_in_error_id>` would always return zero results, which would
  make the audit/history view for entered-in-error records unreachable by status filter.
- **List-vs-detail visibility asymmetry is intentional, not a bug.** `list_terminals_for_circuits`
  (used by `list_circuits`'s computed `circuit_name`/`terminal_count`) excludes entered-in-error
  terminals; `get_circuit`'s own `terminals` array is always unfiltered. Review for: a future PR
  "fixing" `get_circuit` to also filter by status would remove this module's only audit/history view
  for a corrected terminal — a circuit's own detail page is deliberately that view, reachable by id
  regardless of any terminal's status.
- **`frontend/src/modules/substation_registry/pages/SubstationDetailPage.tsx`** — the switchyard
  fetch always requests `include_entered_in_error: true` at the network layer; the "Show
  entered-in-error switchyards" checkbox filters only what is rendered, client-side. Review for: any
  future PR that makes the fetch itself conditional on the checkbox would reintroduce a
  previously-fixed defect — the `(substation_id, voltage_level_id)` uniqueness constraint is not
  status-aware, so `usedVoltageLevelIds` must always see corrected yards or it will re-offer an
  already-taken voltage level as available in the "Add Switchyard" dropdown.
- **UI action naming.** Every correction control reads "Mark as Entered in Error," never "Delete."
  Review for: any future PR introducing a "Delete" label for a persisted record in this module should
  be rejected outright — this module has no concept of an uncommitted draft (every create is one
  atomic, already-committed transaction), so the policy's own draft exception never applies here.
- **No manual browser UAT was performed** for this follow-up, for the same environment reason as
  prior phases. Review for: exercise switchyard correction, circuit terminal correction, the
  reference-protection rejection, and the activation guard in a real browser before this phase is
  frozen/tagged.

### Phase 4 — PSS/E Integration

- **`backend/app/modules/psse_integration/models.py`** — `raw_file_import_batch` ↔
  `topology_version` ↔ `load_snapshot` is a genuine 3-table foreign-key cycle, closed via
  `use_alter=True` on the batch's two forward-pointing columns
  (`fk_raw_file_import_batch_topology_version`/`fk_raw_file_import_batch_load_snapshot`). Review
  for: this was caught only by directly attempting `Base.metadata.create_all()` and observing a
  real `CircularDependencyError` — any future FK added between these three tables (or a fourth
  table joining the cycle) must be re-verified the same way (`create_all` against a throwaway
  SQLite engine), not assumed safe from the model definitions alone. Also review: no P/Q,
  voltage-magnitude/angle, or in-service field exists anywhere on `TopologyBus`/`TopologyBranch`/
  `TopologyTransformer` — a future PR adding one of these "for convenience" (e.g. to avoid a join)
  would violate ADR-003's structural separation and must be rejected.
- **`backend/app/modules/psse_integration/signature.py`** — `compute_topology_signature` is the
  sole authority for "is this the same topology." Review for: any future field added to
  `TopologyBus`/`TopologyBranch`/`TopologyTransformer` that is genuinely structural (not
  operational state) must also be added to the corresponding `_canonical_*_line` function, or two
  structurally different topologies will silently collide on the same signature and incorrectly
  reuse a `TopologyVersion`. Conversely, no operational-state field should ever be added to these
  canonicalization functions — doing so would make momentary state (which naturally varies between
  otherwise-identical imports) incorrectly force a new `TopologyVersion` every time.
- **`backend/app/modules/psse_integration/matching.py`** — the matching algorithm
  (clean_match/unmatched/discrepancy) is this phase's own new design; the reconciled architecture
  docs deliberately left the exact algorithm unspecified. Review for: any future change to the
  candidate-selection or exact-match logic must preserve the "never guess" invariant — ambiguous
  cases (multiple candidates, no exact `ckt_id` match) must always resolve to `discrepancy`, never
  be silently picked by heuristic (e.g. "pick the first candidate," "pick the closest impedance").
  This is the one place in the module where a plausible-looking "improvement" could quietly violate
  ADR-006/ADR-007's mandatory-human-review requirement.
- **`backend/app/modules/psse_integration/service.py`** — `resolve_discrepancy` deliberately never
  writes to Equipment Registry (no cross-module repository/service call, no direct table write) —
  an "accepted" discrepancy only records the engineer's classification on this module's own
  `EquipmentTopologyMap` row. Review for: any future PR that adds a write-through to
  `CircuitTerminal`/`Circuit` from this method (e.g. "auto-correct the voltage yard on accept")
  must be rejected without a new ADR — Equipment Registry's real, current API has no method to edit
  `CircuitTerminal.voltage_yard_id` after creation, and this module must never invent a bypass
  around that immutability. Also review: `_commit_full_topology`'s topology-reuse branch builds
  `branch_lookup`/`transformer_lookup` keyed by PSS/E bus **number** (via a `bus_number_by_id`
  reverse-map from the already-persisted topology), matching the new-topology branch's own key
  space exactly — a prior draft of this method keyed the reuse branch by internal database ids
  instead, which would have silently produced zero `LoadSnapshotElementState` rows on every
  topology-reuse commit; any future refactor of this method must keep both branches' lookup keys in
  the same space.
- **`backend/app/core/queue.py`** — `get_redis_connection()` returns a `fakeredis.FakeRedis()`
  instance whenever `settings.rq_async` is `False`, never a real `redis.Redis` connection. Review
  for: this branch must never be reachable when `rq_async=True` (production) — a future change that
  loosens this condition (e.g. based on `environment` instead of `rq_async`) risks silently running
  production against an in-memory fake queue with no persistence and no real worker process
  consuming it.
- **`backend/app/modules/psse_integration/jobs.py`** — the only file in this module that opens its
  own `SessionLocal()` rather than receiving a request-scoped session via `Depends(get_db)`, since
  RQ jobs run in a worker process outside any FastAPI request. Review for: any future job function
  added here must open and close its own session the same way (never share a session across jobs,
  never accept a session as a parameter) and must not call `db.commit()` from inside
  `PsseIntegrationService` itself — the commit boundary belongs to the job wrapper, exactly as it
  belongs to the router for synchronous endpoints.
- **`backend/alembic/versions/0012_psse_integration.py`** — `psse_import_audit_log.entity_id` is
  `String(80)`, not the more conventional-looking `String(64)` — this was corrected from an initial
  `String(64)` after a real PostgreSQL run (not SQLite) raised `StringDataRightTruncation` on
  `EquipmentTopologyMap`'s composite `"{topology_version_id}:{circuit_terminal_id}"` audit key (73
  characters). Review for: this migration was edited in place before being committed to version
  control (never previously merged), consistent with this project's rule on when in-place migration
  edits are permitted — do not "helpfully" shrink this column back to 64 based on it looking
  oversized; the composite key genuinely needs the extra width. More generally: any future audit
  entry that composes multiple UUIDs into one `entity_id` string must be checked against this same
  column width before being written, and any *new* composite-key pattern introduced elsewhere in
  this codebase should be verified against real PostgreSQL, not assumed safe from SQLite alone —
  this is the second phase in a row (see Phase 3.5/Phase 2's own PostgreSQL-only defects above) where
  SQLite's flexible typing hid a real constraint violation.
- **`backend/app/modules/psse_integration/raw_parser.py`** — designed and verified directly against
  the two real sample files in `docs/samples/psse/`, per this phase's explicit mandate, not against
  generic PSS/E documentation. Review for: any future change to LOAD DATA field-count handling
  (`_STANDARD_LOAD_FIELD_COUNT`/`_ABBREVIATED_LOAD_FIELD_COUNT`/`_MINIMUM_LOAD_FIELD_COUNT`) must be
  re-verified against both real sample files (`test_raw_parser.py`'s own integration tests read
  them directly via a relative path, never a copy) — a plausible-looking fix based on the PSS/E
  spec alone risks silently breaking parsing of the exact abbreviated/"no reading" shapes this
  parser was built to tolerate. Section-boundary tracking is purely terminator-line counting, never
  a fixed section-name list — do not "harden" this into a closed allow-list, which would break
  parsing of any future PSS/E revision's differently-ordered or additional sections instead of
  degrading gracefully to a warning.
- **No manual browser UAT was performed** for this phase, for the same environment reason as every
  prior phase (no browser automation tool available). Review for: exercise the full
  upload → preview → commit → activate flow, and the EquipmentTopologyMap discrepancy-resolution
  workflow, in a real browser against a real backend (with a real Redis/worker, not `fakeredis`)
  before this phase is frozen/tagged — this is also the first phase to exercise a genuine
  asynchronous job-polling UI, which automated RTL tests can only verify against mocked, instantly-
  resolving job responses, not real network latency or a real worker process's timing.

### Future Phases

Every subsequent phase must add its own subsection here, following the
same pattern: file path, one-line reason it is high-risk, and the specific
failure modes reviewers should check for. Do not remove or rewrite a prior
phase's entry — this section is a cumulative record of where GridDefence's
review attention has concentrated, phase by phase.
