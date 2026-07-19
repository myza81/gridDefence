# ADR-025: Stage Setting Trigger — Multiple Frequency/Voltage-Time Operating Criteria per Stage

- **Status:** Accepted
- **Date:** 2026-07-17
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§4 Engineering Truth Before Software Convenience, §5.1 Single Source of Truth, §11.7 Cascading Delete, A5, A13)
- **Depends on:** [ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md) (this ADR corrects, on its own terms, ADR-016's own "Contents" description of a stage setting as exactly one `frequency_threshold_hz`/`voltage_threshold_pu` plus one `time_delay_ms` — it does not reopen ADR-016's decisions about the Stage Setting Set entity, its module ownership, or its three-state lifecycle, all of which are unaffected), [ADR-020](ADR-020-stage-setting-registry-as-standalone-shared-module.md) (module ownership unaffected — the new entity is owned by the same Stage Setting Registry module), [ADR-024](ADR-024-stage-setting-set-draft-deletion.md) (Draft deletion now additionally cascades explicitly, in the same service transaction, through the new child entity — no change to ADR-024's own deletion rule)
- **Affects:** [docs/architecture/stage-setting-set-architecture.md](../architecture/stage-setting-set-architecture.md) (§3, §5–§13, updated in place), [docs/architecture/ufls-architecture.md](../architecture/ufls-architecture.md) (stage display/DTO sections), `docs/engineering/glossary.md` and `docs/engineering/02-engineering-concepts.md` (Stage definition corrected — see Context), `backend/app/modules/stage_setting_registry/` (models, repository, service, router, schemas, exceptions), `backend/app/modules/ufls/` (schemas, service — display only, no change to `UflsStage.stage_setting_id`'s reference target)
- **Informed by:** UFLS UAT, which identified that the as-built one-threshold-per-stage model does not represent real site relay configuration

---

## Context

[ADR-016](ADR-016-stage-setting-set-as-reusable-versioned-entity.md)'s own "Contents" description states a `StageSetting` row carries exactly one `frequency_threshold_hz` (or, for UVLS, one `voltage_threshold_pu`) and one `time_delay_ms` per `stage_order`. `docs/engineering/02-engineering-concepts.md` and `docs/engineering/glossary.md` describe a Stage the same way — "triggered at *a* specific frequency or voltage threshold (with *an* associated time delay)." Both are singular by construction, not by an explicit decision to exclude multiplicity; the six workshops that produced ADR-016 never considered the question because it had not yet surfaced.

UFLS UAT surfaced a real site configuration this model cannot express: a single shedding stage whose relay carries more than one independent operating criterion. The worked example supplied during UAT:

> Stage 8 — 48.1 Hz with 0 ms delay; 49.3 Hz with 60,000 ms delay.

These are not two shedding stages. Both settings belong to the same stage, the same shedding assignment, and the same set of downstream Shedding Actions. The as-built schema forces a second `StageSetting` row with a colliding `stage_order`, which the existing uniqueness rule (correctly) rejects — the software was rejecting a real, valid site configuration, not enforcing a genuine invariant.

**Engineering interpretation — operating semantics.** UAT's own framing states this plainly and this ADR records it as the ratified interpretation, since neither `docs/engineering/` nor `docs/architecture/` previously decided it: each frequency/voltage–time pair configured under a stage is an **independent operating criterion**; satisfaction of **any one** of them constitutes operation of that same stage (an "any-of"/OR relationship — not AND, not voting, not a sequence). This matches standard multi-shot protection relay practice — a fast, low-delay trip at a severe threshold and a slower, longer-delay backup trip at a less severe but sustained threshold, both protecting the same stage's shedding commitment. **GridDefence does not execute or simulate this logic** (`docs/engineering/edr/EDR-004-decision-support-not-automation.md`; `02-engineering-concepts.md`'s own "GridDefence records and enforces the structure of that judgement, it does not compute it") — the semantics matter for correct documentation, correct UI labelling (never implying separate stages, AND logic, or sequencing), and for scoping which validations are structural versus which are the engineer's own judgement. No executable evaluation of this OR logic exists or is introduced by this ADR.

**Monotonicity across stages, with multiple thresholds per stage.** The existing rule — threshold values strictly decrease as `stage_order` increases, within the same region scope — assumed one threshold per stage. Confirmed by the Project Owner during this ADR's own review: each stage's **most severe trigger** (the numerically lowest frequency for UFLS, the numerically lowest per-unit voltage for UVLS — i.e. the trigger that fires earliest/at the least-marginal condition) is the stage's representative value for this comparison. The rule becomes: *the most severe trigger of stage N must be strictly more extreme than the most severe trigger of stage N-1*, within the same region scope. This is a strengthening of the existing guarantee applied consistently to a stage that may now have a range of thresholds, not a relaxation of it, and it makes no assumption about any relationship between individual triggers across stages beyond each stage's own worst case.

## Decision

**A `StageSetting` (one shedding stage within a Stage Setting Set) may own one or more `StageSettingTrigger` rows — each an independent frequency/voltage-time operating criterion for that same stage.** A second operating criterion for stage 8 is a second `StageSettingTrigger` under the existing stage 8 `StageSetting` row; it is never a second `StageSetting` row.

### Terminology

**`StageSettingTrigger`** is adopted for the child entity. Considered against `StageOperatingPoint` and `FrequencyTimeElement`: neither term exists anywhere in `docs/engineering/`, so no established terminology is being overridden. `StageSettingTrigger` is chosen because "trigger" is already the term `docs/engineering/glossary.md`'s own Stage definition uses ("*triggered* at a specific frequency or voltage threshold") — the new entity names the thing that does the triggering, using the project's own existing verb, rather than introducing a new one. It also reads correctly against the parent: a `StageSetting` (the stage) is composed of `StageSettingTrigger` rows (what triggers it).

### Domain model

```
StageSettingSet (1) ──── (many) StageSetting ──── (many) StageSettingTrigger
                              │
                              └── references (read-only, UVLS only) ──▶ Region.region_id
```

- **`StageSetting`** (existing entity, narrowed) retains: `stage_setting_id`, `stage_setting_set_id`, `stage_order`, `region_scope_id`. It no longer carries `threshold_value`, `threshold_unit`, or `time_delay_ms` directly — those move to the child.
- **`StageSettingTrigger`** (new entity): `stage_setting_trigger_id` (UUID PK), `stage_setting_id` (FK to `stage_setting`, `ON DELETE RESTRICT`), `trigger_order`, `threshold_value`, `threshold_unit` (denormalized from the grandparent `StageSettingSet.scheme_type`, unchanged convention), `time_delay_ms`.
- **`UflsStage.stage_setting_id` continues to reference the parent `StageSetting` unchanged.** UFLS assignments (target MW, Shedding Actions) belong to the shedding stage, not to an individual operating criterion — selecting stage 8 gives a UFLS Scheme Version access to every trigger configured under stage 8, with no duplication of the assignment.

### Business rules (supersede/extend `stage-setting-set-architecture.md` §7 rule 4 and §7 rule 5)

1. A `StageSetting` must own at least one `StageSettingTrigger` before the owning Stage Setting Set may be Published (extends the existing "zero `StageSetting` rows" publication block to also require zero-trigger stages be rejected).
2. `trigger_order` is unique within its parent `StageSetting`.
3. The pair (`threshold_value`, `time_delay_ms`) must be unique within its parent `StageSetting` — two operating criteria with identical values are a data-entry error, not a second real criterion.
4. Threshold and time-delay structural validation (`threshold_value > 0`, `time_delay_ms >= 0`) applies per trigger, unchanged in kind from the existing per-setting rule.
5. Between-stage monotonicity (module document §7 rule 4) is evaluated using each stage's most severe trigger (lowest `threshold_value`) as that stage's representative value, compared against the next stage's most severe trigger, within the same region scope group — see Context.
6. No ordering or monotonicity relationship is enforced *between* triggers within the same stage — they are independent criteria, not a sequence; the software records the set the engineer configures without judging its internal relationship, consistent with `02-engineering-concepts.md`'s own "GridDefence records the structure of that judgement, it does not compute it."
7. `ON DELETE CASCADE` remains prohibited (CLAUDE.md §11.7). Draft deletion (ADR-024) now explicitly deletes every owned `StageSettingTrigger`, then every owned `StageSetting`, then the `StageSettingSet` itself, in that order, in one service-layer transaction.

### Migration and historical preservation

A new, additive migration creates `stage_setting_trigger`, backfills exactly one trigger (`trigger_order = 1`) from every existing `StageSetting` row's own `threshold_value`/`threshold_unit`/`time_delay_ms`, then drops those three columns from `stage_setting`. **The old columns are removed, not retained or merely deprecated** — CLAUDE.md §5.1 (Single Source of Truth) prohibits two authoritative copies of the same engineering value existing simultaneously, and a formally-deprecated-but-still-readable column is exactly that: a second copy someone could still read from by mistake. No existing `StageSettingSet`, `StageSetting`, or `UflsStage.stage_setting_id` row is deleted, recreated, or reassigned a new identity by this migration — every stage keeps its own `stage_setting_id`, so every existing UFLS reference remains valid without modification. A Published Stage Setting Set's engineering content (which thresholds and delays it specifies) is bit-for-bit preserved, merely relocated one level deeper in the schema.

## Rationale

**A shedding stage is one engineering decision with, potentially, more than one relay operating criterion protecting it — not two decisions that happen to share a target.** The six ADR-016 workshops correctly identified that a stage's threshold and delay are engineering-owned, versioned data; they did not anticipate that "a stage's threshold and delay" could be a set rather than a scalar, because the site configuration motivating this ADR had not yet surfaced. Narrowing `StageSetting` to stage identity/order/scope and introducing `StageSettingTrigger` for the (now explicitly one-or-many) operating criteria is the direct, minimal correction — it changes cardinality, not any other part of ADR-016's reasoning about why Stage Setting Set exists, how it is owned, or how it is lifecycled.

**Rejecting a second `StageSetting` row with a duplicate `stage_order` as the representation, in favour of a genuine child entity, is required by the domain fact stated directly in the UAT clarification: these are not separate stages.** A second `StageSetting` row would misrepresent stage 8's 49.3 Hz/60,000 ms criterion as an independent shedding stage with its own (implied, incorrect) assignment surface — `UflsStage` would need to reference it separately, duplicating the stage's target MW and Shedding Actions for no engineering reason. The parent-child model keeps exactly one `UflsStage` reference per real shedding stage, which is what CLAUDE.md §5.1 and the domain fact both require.

**`UflsStage.stage_setting_id` is preserved unchanged because UFLS assignments were never about a threshold value — they were always about the stage.** `ufls-architecture.md` already describes `UflsStage` as "referencing... `StageSetting` — threshold, time delay, and stage order are Stage Setting Registry's own owned data," treating the referenced row as the stage's identity, not as a threshold holder. That framing survives this ADR exactly as written; only what `StageSetting` itself now composes changes.

**Monotonicity by most-severe-trigger, not by trigger-order position or by abandoning the check.** Comparing `trigger_order` position across stages (this ADR's own review considered it) would silently assume every stage's operating criteria are configured in a consistent, comparable role-order (e.g. "trigger 1 is always the fast trip") — a convention no authoritative document establishes and no UI input enforces; encoding it would invent a business rule (CLAUDE.md §26). Dropping the check entirely would weaken an already-enforced structural guarantee for every existing single-trigger stage, which this ADR's own instructions explicitly forbid ("do not weaken or remove engineering validation merely to support multiple rows"). Comparing each stage's own worst case preserves the existing guarantee's spirit — later stages are never less severe than earlier ones — without assuming anything about the internal relationship between a stage's own triggers.

## Consequences

**Positive:**
- Represents the real site configuration UAT identified; the software no longer rejects a valid engineering design.
- No duplicated stage/assignment surface — one `UflsStage` row continues to mean one shedding stage, regardless of how many operating criteria protect it.
- Between-stage monotonicity remains software-enforced, strengthened to hold correctly against a stage with a range of thresholds rather than silently becoming meaningless or being removed.
- Migration is purely additive-then-cleanup: no `StageSetting`/`StageSettingSet`/`UflsStage` identity is disturbed; every existing Published Stage Setting Set and every existing UFLS reference remains valid and readable without modification.

**Negative / trade-offs:**
- `ufls-architecture.md`'s and `stage-setting-set-architecture.md`'s existing descriptions of a stage as directly carrying `threshold_value`/`threshold_unit`/`time_delay_ms` are now superseded for this specific aspect (status note, not a rewrite of the rest of either document — module ownership, lifecycle, and every other rule this ADR does not name are unaffected).
- `UflsStageDetail`'s API shape changes from three flat fields (`threshold_value`, `threshold_unit`, `time_delay_ms`) to a `triggers` list — a breaking API/DTO change for any consumer reading those three fields directly (none exist outside the UFLS module's own frontend page at the time of this ADR).
- The Stage Setting Registry's API gains one additional nesting level (stage → triggers) for both read and write; callers creating a new stage design must now perform two calls per stage (create the stage, then add at least one trigger) instead of one, though this matches the real two-step engineering workflow UAT described (settle the stage, then configure its operating criteria).

---

## Alternatives Considered

1. **`StageSetting` owns one or more `StageSettingTrigger` rows, exactly as decided above.** **Adopted.** Matches the UAT-supplied domain fact directly, preserves `UflsStage`'s existing reference target, and requires no change to any other module's own dependency direction (CLAUDE.md A2) — the new entity is owned by the same Stage Setting Registry module as before (ADR-020 unaffected).

2. **Represent a second criterion as a second `StageSetting` row, relaxing `stage_order` uniqueness to allow duplicates.** **Rejected.** Explicitly contradicted by the UAT clarification itself ("these are not separate shedding stages"); would force `UflsStage` to reference criteria individually, duplicating assignment data with no engineering meaning, and would make "how many shedding stages does this set have" an ambiguous question the schema could no longer answer directly.

3. **Store multiple thresholds as a JSON/array column on `StageSetting` rather than a genuine child entity.** **Rejected.** Fails CLAUDE.md §11.8 (every business rule the database can enforce, should be) — uniqueness of `trigger_order`, uniqueness of the (`threshold_value`, `time_delay_ms`) pair, and per-trigger `CHECK` constraints all require real rows, not an opaque blob only the application layer can validate. Also forfeits per-trigger audit history (module document §12), which an array column cannot express at the same granularity as the existing per-`StageSetting` audit pattern.

4. **Compare `trigger_order` position across stages for monotonicity, instead of each stage's most severe trigger.** **Rejected**, per Rationale above — assumes an unestablished convention that `trigger_order` carries a consistent engineering role across every stage in a set.

5. **Retain the old `threshold_value`/`threshold_unit`/`time_delay_ms` columns on `StageSetting` as deprecated compatibility columns after backfill.** **Rejected.** Directly creates the two-authoritative-copies problem CLAUDE.md §5.1 exists to prevent — a caller could read the stale scalar column instead of the real, potentially-multi-row trigger set and silently see an incomplete (single-criterion) picture of a multi-criterion stage.
