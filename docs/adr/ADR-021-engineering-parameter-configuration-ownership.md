# ADR-021: Engineering Parameter Configuration Ownership

- **Status:** Accepted — implemented (Shared Platform Sprint 1)
- **Date:** 2026-07-15
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§22, A5, A7 — engineering parameters belong in the database, versioned, auditable, never hidden in `.env`; the principle this ADR gives a concrete home)
- **Depends on:** none directly; elaborates CLAUDE.md A7, which already establishes the principle but not the module that realizes it
- **Affects:** [docs/architecture/continuous-evaluation-architecture.md](../architecture/continuous-evaluation-architecture.md) §7.1 (the MW tolerance's own "belongs in Core Platform's engineering-parameter configuration surface" note is now realized concretely, not merely gestured at), [docs/architecture/scheme-data-consumption-matrix.md](../architecture/scheme-data-consumption-matrix.md) (gains a new row)
- **Informed by:** the Shared Defence-Scheme Platform Implementation Readiness Review, which found no existing module owns this shape of data

---

## Context

CLAUDE.md A7 already draws the line between Infrastructure Configuration (environment variables — database URL, secret keys, log level) and Engineering Parameters (database-stored, versioned, auditable, visible to authorised users — UFLS/UVLS/EMLS thresholds, the Continuous Evaluation Engine's own MW tolerance). [`continuous-evaluation-architecture.md`](../architecture/continuous-evaluation-architecture.md) §7.1 names the ±10% MW tolerance as exactly this kind of data and says it "belongs in Core Platform's engineering-parameter configuration surface" — but no such surface exists in the current codebase. `app/reference_data/` is the only existing Core Platform data module, and its own shape (`VoltageLevel`, `Region`, `State`, `GmZone`, `GridOwner`, `OperationalStatus`, `LineType`, `TransformerBreakerNumberingConvention`) is uniformly: SMALLINT/INTEGER-keyed, idempotently bulk-seeded via `app/reference_data/seed.py`, rarely changed, and — critically — **not individually audited**. An engineering parameter (a tolerance value an Administrator changes deliberately, rarely, with a reason) is a different shape of data entirely.

## Decision

**Engineering Parameter Configuration is a new, small, standalone module — never folded into `reference_data`.**

- **Module ownership:** a new `app/modules/engineering_parameters/` module (Core Platform tier, alongside IAM and Reference Data in the domain hierarchy — CLAUDE.md §7 — referenced by every module above it, dependent on nothing scheme-specific).
- **Entity shape:** one row per named parameter — `parameter_key` (stable string identity, e.g. `mw_tolerance_percentage`), `value` (numeric or string, per parameter), `unit` (display convenience), `description`, `updated_by_user_id`, `updated_at`. Not a lookup table (CLAUDE.md A5) — a small set of individually-identified, individually-audited business values. `parameter_key` is the natural primary key (a short, stable, human-legible string, mirroring `Permission.permission_id`'s own precedent of a string PK for a small, code-referenced catalog — not every business entity requires a UUID surrogate, per CLAUDE.md A5's own "reference and lookup tables... do not require UUIDs unless there is a specific architectural reason," and a parameter key is exactly the kind of stable, code-referenced identity that reasoning already covers).
- **Lifecycle:** current-value-plus-audit-log, not a Draft/Published state machine. Every change is a single, atomic, audited write (old value, new value, actor, mandatory non-empty reason, timestamp) — mirroring `SubstationService.change_status`'s and `IAMService.set_user_status`'s own already-established "single audited transition" pattern, not Scheme Version's heavier four-state lifecycle. A tolerance value has no Draft state to iterate on and nothing to Publish — it is either the current value or it is not; a full lifecycle state machine here would be exactly the premature complexity CLAUDE.md §21 warns against.
- **Auditing:** its own `engineering_parameter_audit_log`, per CLAUDE.md A4 — one row per change, in the same shape every other module's own audit log already uses.
- **Permissions:** read is broadly available (any authenticated user — the Engineering Review Panel and Engineering Workspace both need to display the current tolerance to any engineer). Write requires a new, elevated, admin-tier permission — `engineering_parameters.manage` — distinct from ordinary Editor-tier scheme-design permissions, mirroring the same elevated-tier reasoning [findings-and-publication-governance-architecture.md](../architecture/findings-and-publication-governance-architecture.md) §4.1 already established for `PublicationTreatmentPolicy` changes. Changing an engineering parameter is a platform-wide policy decision, not an ordinary scheme-design action.
- **Versioning:** none beyond the audit log. The audit log itself already answers "what was the tolerance on date X" for any historical reproducibility need (CLAUDE.md §5.4) — a separate versioned/Draft concept would duplicate what the audit log already provides.
- **API surface:** `GET /engineering-parameters/{key}` (read, any authenticated user); `GET /engineering-parameters` (list, any authenticated user); `PUT /engineering-parameters/{key}` (write, `engineering_parameters.manage`, mandatory `change_reason` in the request body, mirroring `SubstationStatusChange`'s own established request shape); `GET /engineering-parameters/{key}/audit-log` (read, gated the same as the write action — changing a platform-wide policy value's history is itself sensitive, mirroring [findings-and-publication-governance-architecture.md](../architecture/findings-and-publication-governance-architecture.md) §13's "audit log access is itself access-controlled").
- **Database ownership:** two tables, `engineering_parameter` and `engineering_parameter_audit_log`, owned exclusively by this new module's own service layer (CLAUDE.md A1) — no other module writes to either table directly.

### Why not Reference Data

Explicitly rejected, for three concrete reasons, not merely a style preference:
1. **Audit shape mismatch.** `reference_data`'s existing rows are seeded idempotently and never individually audited — there is no `region_audit_log`, and there should not be one, since a Region's own catalog entry is not the kind of value an Administrator "changes with a reason" the way a tolerance is. Retrofitting per-row audit onto `reference_data` to accommodate engineering parameters would be a larger, riskier change than adding one new small module.
2. **Permission shape mismatch.** `reference_data`'s own write path (`seed.py`, run manually, per `README.md`'s own documented deployment step) has no runtime, permission-gated API write endpoint at all today — every existing reference table is administered by re-running the seed script, not by an authenticated user action through the application. An engineering parameter, by contrast, must be changeable by an authorised Administrator through the running application, audited, without a deployment step. These are two different operational models; conflating them would force one of the two to adopt the other's shape awkwardly.
3. **Conceptual mismatch.** `reference_data` answers "what are the valid values for this classification" (a Region, a Voltage Level) — closed enumerations the application selects from. Engineering Parameter Configuration answers "what is the currently-approved numeric/textual value of this named engineering setting" — a single current fact, not a set of valid choices. CLAUDE.md A7 already treats these as two different categories (Reference Data in §11.3; Engineering Parameters in A7) — this ADR keeps that distinction intact in code, not just in principle.

## Rationale

**This ADR gives CLAUDE.md A7 a concrete home for the first time, rather than leaving the principle unrealized.** A7 has stood, unimplemented, since the platform's earliest standards were written — the MW tolerance is the first engineering parameter this codebase actually needs, and without a decision now, the natural but wrong path is to bolt it onto whichever module happens to need it first (Continuous Evaluation), which would make the tolerance appear to be Continuous Evaluation's own owned data rather than genuinely shared, audited, platform-wide configuration any future module might also need (a validated threshold range, per `ufls-module.md`'s own long-standing recommendation that such bounds be stored, not hardcoded).

**A small, standalone module is proportionate to a small amount of genuinely different data — this is not over-engineering.** One table, one audit log, one elevated permission, no lifecycle machinery beyond what a single audited value change already needs. CLAUDE.md §21's "avoid premature optimisation... unnecessary abstraction" cuts the other way here too: cramming this shape into `reference_data` to avoid a second small module would itself be a premature generalization, forcing two genuinely different data shapes to share one module's own conventions.

## Consequences

**Positive:**
- Gives every future engineering-parameter need (validated threshold ranges, future scheme-type-specific tolerances) one obvious, already-audited home, closing this gap once rather than per parameter.
- `continuous-evaluation-architecture.md` §7.1's own "belongs in Core Platform's engineering-parameter configuration surface" note is now concrete and implementable, not aspirational.
- Small enough to build in one short sprint, with no dependency on any other new Shared Platform capability.

**Negative / trade-offs:**
- One more small module in the codebase, with its own migration, service, router, and bootstrap — a genuine, if small, addition to the module count.
- Every future engineering parameter must be added as a new `parameter_key` row (or a schema addition, if a parameter needs a materially different shape than key/value/unit/description) rather than a dedicated column on some other module's table — an intentional constraint, not an oversight, since it keeps every engineering parameter discoverable in one place rather than scattered per consuming module.

---

## Alternatives Considered

1. **New, standalone `engineering_parameters` module, as decided above.** **Adopted.** Matches CLAUDE.md A7's own category distinction exactly; small, proportionate, immediately reusable by future parameters.

2. **Fold into `reference_data`.** **Rejected** — see "Why not Reference Data," above: audit shape, permission shape, and conceptual shape all mismatch.

3. **Fold into the Continuous Evaluation Engine itself, as a local configuration table owned by that module.** **Rejected.** The MW tolerance is not Continuous Evaluation's own engineering fact — treating it as Continuous-Evaluation-owned would misclassify a platform-wide policy value as one module's private configuration, and would force a future consumer (e.g. a validated threshold range a scheme module needs, unrelated to MW evaluation) to depend on the Continuous Evaluation Engine module for an unrelated reason.

4. **Environment variable / `.env`.** **Rejected outright, not seriously entertained.** CLAUDE.md A7 already forbids this explicitly and unconditionally for engineering parameters specifically — this ADR does not reopen that decision, only realizes it.
