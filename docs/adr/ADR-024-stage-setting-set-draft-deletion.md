# ADR-024: Stage Setting Set Draft Deletion

- **Status:** Accepted
- **Date:** 2026-07-17
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§11.6 Soft Delete, §11.7 Cascading Delete, A13 ADR requirement for versioning changes)
- **Depends on:** [ADR-015](ADR-015-defence-scheme-version-lifecycle-simplification.md) (this ADR applies ADR-015's own "a never-Published Draft carries no historical weight" reasoning to a second, independent entity — it does not reopen or generalize ADR-015 itself), [ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md) (this ADR extends, but does not reopen, the three-state lifecycle ADR-016 established)
- **Affects:** [docs/architecture/stage-setting-set-architecture.md](../architecture/stage-setting-set-architecture.md) §6, §10 (updated in place — see Consequences), `backend/app/modules/stage_setting_registry/` (service, repository, router, exceptions), `backend/app/modules/ufls/service.py` and any future `uvls` module's equivalent (selection-time validation correction)
- **Informed by:** UFLS UAT, which identified both the Draft-abandonment governance gap this ADR resolves and a documentation/implementation divergence in Stage Setting Set selection-time validation (resolved here as a companion correction, §"Selection-Time Validation Correction" below)

---

## Context

[ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md) gave Stage Setting Set a three-state lifecycle (`Draft → Published → Entered in Error`) but never decided whether a `Draft` Stage Setting Set could be deleted. In practice, UFLS UAT surfaced this as a real operational gap: an engineer who creates a Stage Setting Set with the wrong scheme type, or abandons a design mid-edit, has no way to remove it. It can only be left in `Draft` forever or published as-is.

[ADR-015](ADR-015-defence-scheme-version-lifecycle-simplification.md) already decided this exact question for a different entity (Defence Scheme Version) — *"Drafts may be deleted... an abandoned Draft is neither [an approved engineering record nor a historical record]"* — but explicitly scoped that decision: *"Permitting deletion here does not create a precedent for any other versioned entity in the platform."* Stage Setting Set therefore requires its own ADR to authorize the same category of exception, argued on its own terms, per CLAUDE.md A13.

A companion investigation (an architecture review performed before this ADR, not repeated here) also found a live divergence between `stage-setting-set-architecture.md` §6's stated rule — *"[Draft is] not yet referenceable by any Scheme Version"* — and the as-built `UflsService`, which validates only that a selected Stage Setting Set's `scheme_type` matches, not that its `status` is `PUBLISHED`. This ADR resolves that divergence as well (§"Selection-Time Validation Correction"), since it is a precondition for reasoning cleanly about reference-blocking during deletion.

## Decision

**A Stage Setting Set may be physically deleted if, and only if, its lifecycle status is `DRAFT`.**

- **Published and Entered in Error remain permanent, immutable engineering records** — physical deletion is illegal from either state; the existing `Entered in Error` transition remains the sole correction mechanism for anything that has ever carried engineering authority. Nothing about this ADR changes Published/Entered-in-Error behaviour.
- **No new lifecycle state is introduced.** `Abandoned`, a soft-delete flag, or a retirement flag are all explicitly rejected — mirroring ADR-016's own rejection of a `Superseded` state for this entity (*"would either be permanently unused... or would need its own, separately-invented trigger condition"*). A deleted Draft simply ceases to exist; there is no intermediate state to query, filter, or audit against, only the audit log entry recording that the deletion happened (below).
- **Deletion requires `stage_setting_registry.manage`** — the same permission that already gates Draft creation and Draft editing (add/update/remove/reorder settings). This mirrors the already-shipped precedent: `UflsService.delete_draft_version` is gated by `ufls.manage`, the same permission as ordinary Draft editing, not a separate, more-privileged permission. Deleting one's own unpublished Draft is Draft-editing, not a lifecycle correction — it does not require the elevated trust `stage_setting_registry.publish`/`.enter_in_error` represent.
- **Deletion is blocked if the Stage Setting Set is referenced by any UFLS or UVLS Scheme Version, regardless of that Scheme Version's own lifecycle state.** The service layer performs an explicit pre-check, through each scheme module's own service-layer interface (CLAUDE.md A1 — never a direct cross-module repository query), and raises a structured domain error before any deletion is attempted. The database's own `ON DELETE RESTRICT` constraints on `stage_setting_set_id`/`stage_setting_id` remain the final integrity guarantee regardless of whether the service-layer pre-check is ever bypassed or incomplete — this ADR does not relax or replace that constraint.
- **Deletion is audited.** `stage_setting_registry_audit_log` (CLAUDE.md A4) records the deleted Stage Setting Set's own identifier, identifying metadata sufficient for traceability (scheme type, description, and setting count at time of deletion — the row itself no longer exists to look this up after the fact), the actor, the timestamp, and the action type (`deleted`). This mirrors `UflsService.delete_draft_version`'s own established pattern of auditing a Draft deletion even though the deleted record itself is not historically significant — the *act* of deletion is an administrative action requiring traceability, independent of whether its subject was.
- **Owned `StageSetting` child rows are deleted explicitly, in the same service-layer transaction, before the parent `StageSettingSet` row.** CLAUDE.md §11.7 prohibits `ON DELETE CASCADE` on engineering entities; this ADR does not introduce one. The service performs both deletions itself, atomically, relying on `ON DELETE RESTRICT` (not `CASCADE`) to reject the whole transaction if any child `StageSetting` is, in fact, still referenced by a `UflsStage`/future `UvlsStage` row despite the parent-level pre-check.

### Selection-Time Validation Correction

**A UFLS or UVLS Scheme Version may select only a `PUBLISHED` Stage Setting Set of the matching scheme type.** `DRAFT` and `ENTERED_IN_ERROR` Stage Setting Sets, a scheme-type mismatch, and a missing Stage Setting Set are all rejected at selection time (`update_version_metadata` and equivalent), with a structured domain error — never merely deferred to the Publish-time prerequisite check. This resolves the divergence in favour of `stage-setting-set-architecture.md` §6's originally-stated rule, rather than rewriting that rule to match the as-built gap.

This correction is a precondition for the deletion decision above to be sound: with it in place, a `DRAFT` Stage Setting Set can never legitimately be referenced by any Scheme Version, so the reference-block check on deletion is defense-in-depth (protecting against any future regression of this rule, or a row created before this correction shipped), not a routinely-triggered path.

**This does not change historical read behaviour.** An already-Published Scheme Version that referenced a Stage Setting Set which has since been marked `Entered in Error` remains fully readable and unaffected (ADR-016 §7 rule 2/3, unchanged) — this correction governs only the moment of *selecting* a reference on a still-editable Draft Scheme Version, never the interpretation of an existing, already-committed reference.

## Rationale

**A never-Published Stage Setting Set Draft is temporary working material, not a permanent engineering record — the identical reasoning ADR-015 already applied to Defence Scheme Version Drafts, restated here on Stage Setting Set's own terms rather than borrowed by analogy.** `docs/engineering/02-engineering-concepts.md`'s own description of a Working Draft — *"It has no operational authority... without any risk of a half-finished idea being mistaken for an approved engineering decision"* — describes exactly the same pre-authority state a Draft Stage Setting Set occupies. CLAUDE.md §5.2 (Immutable Engineering History) protects records that governed real behaviour or were seriously reviewed as candidates to; a Draft Stage Setting Set, so long as it remains selectable only by other Drafts (a state ADR-015 already treats as equally non-authoritative) and never by a Published version, has done neither.

**Requiring the selection-time correction as part of this same ADR, rather than as an independent follow-up, keeps the reference-blocking rule honest.** Without it, a Draft Stage Setting Set could legitimately be mid-use by another module's own Draft — not historically significant, but operationally live — and "blocked if referenced" would need to reason about partial, in-progress use rather than a clean boundary. Fixing selection-time validation first (or atomically alongside deletion) means "referenced" and "Published" become synonymous for any row created after this ADR ships, and the reference-block check becomes a pure integrity backstop rather than a routinely-necessary business rule.

**No `Abandoned` state, for the same reason ADR-016 already gave for rejecting `Superseded`.** Both would be states with no engineering meaning distinct from non-existence — queryable clutter that governs nothing, referenced by nothing, and answers no question an engineer or auditor would actually ask. The audit log entry already provides everything a hypothetical `Abandoned` state could offer (a permanent record that a deletion happened) without the ongoing cost of a row that must be displayed, filtered, and reasoned about forever.

**`stage_setting_registry.manage`, not a new, more-privileged permission, because deletion is Draft-editing, not correction.** `stage_setting_registry.publish` and `.enter_in_error` are deliberately more privileged than `.manage` because they act on a record that has, or is about to, gain real engineering authority. A Draft delete never crosses that boundary — it is the same tier of action as adding or removing a `StageSetting` row, which `.manage` already governs.

## Consequences

**Positive:**
- Closes the UAT-identified governance gap: an engineer can now correct or abandon a mistaken Draft Stage Setting Set without administrator escalation, exactly mirroring the already-shipped UFLS Draft-version-deletion workflow.
- Resolves the `stage-setting-set-architecture.md` §6 / as-built divergence in favour of the originally-documented, more conservative rule, closing a real correctness gap independent of deletion (a Draft Stage Setting Set's content could previously change under an in-progress UFLS Draft without that Draft's own knowledge, since nothing pinned the reference to immutable, Published content).
- No new lifecycle machinery, no schema change, no new permission — the smallest change that fully resolves both the deletion gap and the validation divergence.

**Negative / trade-offs:**
- The selection-time correction is a behaviour change: a UFLS/UVLS Draft version that, before this ADR, referenced a still-Draft Stage Setting Set will, going forward, be unable to *newly* select one. Any pre-existing Draft Scheme Version row already referencing a Draft Stage Setting Set (a state now only reachable from before this correction shipped) is not retroactively invalidated by this ADR — it remains exactly as blocked from Publishing as it already was under the pre-existing `UFLS_STAGE_SETTING_SET_PUBLISHED` prerequisite, and simply cannot happen again for a new selection.
- `stage_setting_registry_audit_log` will contain `deleted` entries whose subject row no longer exists — any future audit-log UI must render these from the audit entry's own captured metadata, not by joining back to `stage_setting_set` (which the delete-detail metadata requirement above exists specifically to make possible).

---

## Alternatives Considered

1. **Physical deletion of Draft records only, exactly as decided above.** **Adopted.** Matches the ratified Project Owner decision, mirrors the already-shipped ADR-015/UFLS precedent on its own terms (not by unauthorized analogy), and introduces no new state or schema.

2. **`Draft → Abandoned` lifecycle transition.** **Rejected.** Carries the identical "permanently unused or needs an invented trigger" problem ADR-016 already used to reject `Superseded` for this entity. An `Abandoned` Stage Setting Set would be governed by nothing, referenced by nothing, and would exist solely as clutter every future list/audit view must account for.

3. **Soft-delete flag (e.g. `is_deleted`) distinct from `status`.** **Rejected.** Duplicates the lifecycle status column's own job and contradicts CLAUDE.md §11.6's binary framing ("physically deleted" vs. "lifecycle status represents retirement") by introducing a second, parallel deletion signal outside the lifecycle model ADR-016 already established.

4. **Leave selection-time validation as-is (scheme-type check only), rely solely on the Publish-time prerequisite.** **Rejected.** This is the as-built divergence itself, not a resolution of it — it contradicts `stage-setting-set-architecture.md` §6's own documented rule and would leave the deletion reference-check reasoning about live, in-progress cross-module use rather than a clean Published/unreferenced boundary.
