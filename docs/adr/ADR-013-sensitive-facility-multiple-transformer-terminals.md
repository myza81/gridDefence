# ADR-013: Sensitive Facility Supports Multiple Current Transformer Terminal Associations

- **Status:** Accepted — implemented (Phase 3.7 UAT change request)
- **Date:** 2026-07-11
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.4, §11.2, §21, A1, A4, A13)
- **Amends:** [ADR-012](ADR-012-sensitive-customer-registry-architecture.md) decision 2 (attachment granularity). ADR-012's original text is preserved unmodified below its own content, per this project's practice of never rewriting historical decision text (CLAUDE.md §5.2) — this ADR records the amendment as a new decision, not a silent edit of ADR-012.
- **Related:** [`sensitive-customer-registry-module.md`](../architecture/sensitive-customer-registry-module.md), [`sensitive-customer-registry-implementation-spec.md`](../architecture/sensitive-customer-registry-implementation-spec.md), [EDR-008](../engineering/edr/EDR-008-sensitive-customer-registry-scope.md) (unaffected — the registry's scope/purpose does not change).

---

## Context

During manual UAT of Phase 3.7, the Project Owner identified that the single-Transformer-Terminal attachment ADR-012 decision 2 established does not faithfully represent the real engineering relationship for facilities supplied by more than one currently active Transformer Terminal (e.g. a large or dual-fed facility). ADR-012 decision 2 itself anticipated this possibility explicitly:

> "Should a future engineering requirement introduce alternate or multiple concurrent supply arrangements, the architecture should be able to evolve by extending that association... rather than requiring a fundamental redesign of `SensitiveFacility` or of this module's service interface."

module doc §19 open question 5 asked exactly when this constraint should be revisited. The Project Owner has now answered that question directly, with the authority CLAUDE.md §23 assigns the Project Owner ("Approves engineering decisions. Owns product direction.").

**This is not the alternate-supply modelling ADR-012 decision 2 declined to build.** Alternate-supply modelling implies a facility has designated primary/backup/standby supply arrangements with priority semantics. This decision introduces no such thing — it records that a physical facility may, as an engineering fact, be currently and simultaneously fed by more than one Transformer Terminal, with every recorded association being an equally-weighted, currently-active fact. It is also not supply-history modelling — no validity window, no point-in-time query, no record of a terminal a facility was *previously* associated with. When an association is removed, it is gone from the current-state table; the *fact that it was removed, when, by whom, and why* is preserved only in the audit log, exactly as a terminal reassignment already was under the single-terminal model.

## Decision

**`SensitiveFacility` associates with zero or more currently active Transformer Terminals**, via a new association table `sensitive_facility_transformer_terminal`, replacing the single nullable `transformer_terminal_id` foreign key ADR-012 decision 2 established.

1. **Association table, not a richer historical link.** `sensitive_facility_transformer_terminal(facility_id, transformer_terminal_id, added_at, added_by_user_id)` — composite primary key, current-state only, mirroring IAM's own `RolePermission` join-table pattern (simple grant/revoke, no validity window) rather than `UserRole`'s historical-retention pattern (`revoked_at`). This is a deliberate choice: `UserRole`'s pattern exists because a *past* role grant remains meaningful (audit reconstruction of "who had what access, when"); this registry's own audit log already serves that exact purpose for terminal associations, so the join table itself carries no historical burden.

2. **The reference remains a reference, never an owned identity.** Each row still points at Equipment Registry's `TransformerTerminal` by ID only (CLAUDE.md A1) — this decision changes cardinality, not ownership. ADR-012's core placement decision (independent bounded context, Master Data domain, no GridDefence vocabulary) is entirely unaffected.

3. **Every association change is audited individually.** Adding or removing one association writes one audit row (`subject_type='SENSITIVE_FACILITY'`, `field_name='transformer_terminal_id'`, `old_value`/`new_value` naming the terminal added or removed) with a mandatory, non-empty reason — continuing, not weakening, the mandatory-reason discipline ADR-012's original reassignment rule established. A multi-terminal edit (the frontend's multi-select "Save") is exposed as one API call that internally diffs the requested target set against the current set and writes one audit row per actual change — never a single bulk "set changed" event that would obscure which specific terminal was added or removed.

4. **Resolution status becomes per-terminal, not per-facility.** `transformer_terminal_resolution` (`NOT_ASSIGNED`/`RESOLVED`/`UNRESOLVED`, Correction 4 of the implementation spec) no longer describes the facility as a whole — a facility with two associated terminals could have one resolved and one stale. Each association is now independently reported with its own resolution status and identity. A facility-level aggregate remains available for list filtering (`NOT_ASSIGNED` = zero associations; `RESOLVED` = one or more associations, all resolved; `UNRESOLVED` = one or more associations, at least one unresolved), but the detail/list response itself always exposes the full per-terminal breakdown — Correction 4's governing rule ("never silently omit or collapse an unresolved condition") now applies per association, not just per facility.

5. **Batch and single lookup semantics: "any associated terminal matches."** `get_sensitive_facilities_for_transformer_terminal(id)` and the batch equivalent now match a facility if *any* of its associated terminals equals the requested ID — a facility with terminals A and B appears under both A's and B's batch-lookup key. This is the natural generalisation of the existing single-terminal contract, not a new concept; no scheme-specific interpretation is introduced by this ADR (ADR-012 decision 4 is unaffected — the registry still returns facts, never verdicts).

## Rationale

The Project Owner's own framing is the primary rationale and is adopted as this ADR's own: this refinement makes the data model match the real engineering relationship (a physical facility can genuinely be fed by more than one currently active terminal) without introducing any of the concepts ADR-012 and the Agreed Engineering Principles explicitly declined — no priority/primary-secondary logic, no historical supply modelling, no automatic topology inference, no scheme-specific interpretation. ADR-012 decision 2 itself reserved exactly this extension path rather than foreclosing it, so this is the anticipated evolution, not an unplanned architectural drift.

## Consequences

**Positive:**
- The registry now records the true current-state engineering fact for multi-fed facilities, which the single-terminal model could not represent at all (it would have forced an arbitrary, misleading choice of "the" terminal).
- The association table pattern (mirroring `RolePermission`) is a well-understood, already-proven shape in this codebase — no new architectural pattern is introduced.
- Per-terminal resolution reporting is strictly more informative than the prior per-facility flag, and required no change to Correction 4's governing principle, only its unit of application.

**Negative / trade-offs:**
- Every place that previously read a single `transformer_terminal_id` (backend schemas, API responses, frontend forms and tables) requires a corresponding collection-shaped change — a mechanical but wide-reaching migration across the full stack.
- The "at least one unresolved" aggregate used for facility-level filtering is a coarser signal than the full per-association detail; a UI relying only on the aggregate could miss which specific association is stale. Mitigated by always exposing the full per-terminal list in list/detail responses, never only the aggregate.
- The migration touches an uncommitted, unmerged table (`sensitive_facility`, from migration `0015`) — per this project's own established practice for pre-merge migrations (`0014_alsf_registry`'s own precedent), migration `0015` is edited in place rather than superseded by a new migration, since it has never been committed to `main`.

## Alternatives Considered

1. **Add a second nullable `transformer_terminal_id_2` column (or a small fixed number of slots).** Rejected — this is exactly the kind of ad hoc, non-extensible modelling CLAUDE.md §21 and this module's own precedent (ADR-012 decision 2's own reasoning) already reject; a real association table is barely more implementation effort and is unbounded, auditable, and queryable in the standard way.
2. **Keep a single "primary" terminal plus a separate list of "additional" terminals.** Rejected — this reintroduces a priority/primary concept the Project Owner explicitly excluded ("Do not introduce active/standby logic"). Every association is equally weighted; there is no primary.
3. **Retain `UserRole`'s validity-window (`revoked_at`) shape for the association table.** Rejected — this would be supply-*history* modelling, which the Project Owner explicitly excluded. The audit log already preserves the history of additions and removals; the association table itself needs only to answer "what is currently associated," not "what was ever associated and when."

## Implementation Note

This ADR is implemented directly in migration `0015_sensitive_customer_registry.py` (edited in place, not superseded — see Consequences), `backend/app/modules/sensitive_customer_registry/{models,schemas,repository,service,router}.py`, and the corresponding frontend module. See `sensitive-customer-registry-implementation-spec.md` for the concrete, as-built shape this ADR authorises.
