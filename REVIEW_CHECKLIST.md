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

### Future Phases

Every subsequent phase must add its own subsection here, following the
same pattern: file path, one-line reason it is high-risk, and the specific
failure modes reviewers should check for. Do not remove or rewrite a prior
phase's entry — this section is a cumulative record of where GridDefence's
review attention has concentrated, phase by phase.
