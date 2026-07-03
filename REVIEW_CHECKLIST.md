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

### Future Phases

Every subsequent phase must add its own subsection here, following the
same pattern: file path, one-line reason it is high-risk, and the specific
failure modes reviewers should check for. Do not remove or rewrite a prior
phase's entry — this section is a cumulative record of where GridDefence's
review attention has concentrated, phase by phase.
