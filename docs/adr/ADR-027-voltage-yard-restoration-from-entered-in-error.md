# ADR-027: Voltage Yard Restoration from Entered in Error

- **Status:** Accepted
- **Date:** 2026-07-23
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§4 Engineering Truth Before Software Convenience, §5.2 History Is Preserved, §11.3 Reference Tables, §11.6 No Hard Delete)
- **Affects:** [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) ("Phase 3 Follow-up: Deletion/Correction Policy"), `backend/app/modules/equipment_registry/` (service, exceptions, schemas, router), `frontend/src/modules/substation_registry/pages/SubstationDetailPage.tsx`
- **Relates to:** [ADR-008](ADR-008-substation-voltage-yard.md) (the Voltage Yard entity and its `(substation_id, voltage_level_id)` identity), [ADR-014](ADR-014-substation-lifecycle-simplification.md) (the closed substation transition allow-list this ADR mirrors), the Deletion/Correction Policy (Phase 3 follow-up) that introduced `ENTERED_IN_ERROR`

---

## Context

The Deletion/Correction Policy introduced `ENTERED_IN_ERROR` so that a mistakenly-created engineering record could be corrected without a hard delete (CLAUDE.md §11.6). The status is seeded with `is_terminal = true`, and every entity that owns a lifecycle allow-list treats it as terminal: Substation Registry's `_STATUS_TRANSITIONS` maps `"ENTERED_IN_ERROR": set()` (ADR-014), and IAM, Scheme Platform, Stage Setting Registry and Sensitive Customer Registry each enforce the same "no transition out" rule in their own modules.

`SubstationVoltageYard` was given `operational_status_id` by that same policy, but **no transition allow-list was ever added for it**. Two consequences followed, both undesirable:

1. **Governance gap.** `EquipmentRegistryService.update_voltage_yard` accepted *any* valid status in place of *any* other. The only guard (`_require_no_active_references_to_voltage_yard`) fires solely when moving **into** `ENTERED_IN_ERROR`. A yard could therefore be moved to `MOTHBALLED`, `RETIRED`, or back to `ACTIVE` with no rule applied at all — the permissiveness was an omission, not a designed capability.

2. **An unrecoverable state if terminality were simply enforced.** A Voltage Yard's identity is `(substation_id, voltage_level_id)`, protected by `UniqueConstraint("substation_id", "voltage_level_id")` **and** by a service pre-check (`voltage_yard_exists_for_substation_and_level`) that is **status-blind** — it matches an `ENTERED_IN_ERROR` row exactly as it matches an active one. A corrected yard therefore **permanently occupies its identity slot**: no replacement can ever be created for that substation at that voltage level.

This is where a Voltage Yard differs structurally from every other entity that treats `ENTERED_IN_ERROR` as terminal. A mistakenly-created **Substation** is re-created under a different mnemonic; a mistaken **Circuit** or **Transformer** is re-created with a different bay/transformer number. A Voltage Yard has **no alternative identity** — the correct record for a real 33kV switchyard at BTIN *is* `(BTIN, 33kV)` and can be nothing else. If the act of marking it Entered in Error was itself the mistake, enforcing terminality without a restoration path would leave GridDefence permanently unable to represent a switchyard that physically exists — the registry would be locked into a known-false state, which CLAUDE.md §4 (Engineering Truth Before Software Convenience) does not permit.

## Decision

**Substation Voltage Yards get an explicit, closed transition allow-list containing exactly two edges — and `ENTERED_IN_ERROR → ACTIVE` is one of them.**

```
ACTIVE            → { ENTERED_IN_ERROR }
ENTERED_IN_ERROR  → { ACTIVE }
```

- **Every other transition is rejected**, including from any status not listed above, with `InvalidVoltageYardStatusTransitionError` — Equipment Registry's own equivalent of Substation Registry's `InvalidStatusTransitionError`, defined locally per the established per-module convention (CLAUDE.md A1: no cross-module Python imports).
- **A same-status update is an idempotent no-op with no audit row**, mirroring `SubstationService.change_status` exactly.
- **`change_reason` is mandatory in both directions.** Marking a yard Entered in Error and restoring it are both consequential lifecycle corrections; neither may be recorded without a stated reason.
- **Restoration targets `ACTIVE` deterministically.** The pre-error status is not recovered by parsing audit history: yards are only ever created `ACTIVE`, so `ACTIVE` is the only meaningful restoration target, and inferring one from history would add a failure mode for no engineering gain. The audit log remains the record of what happened.
- **Restoration is refused when the parent Substation is in a terminal lifecycle state** (`operational_status.is_terminal = true` — today `DECOMMISSIONED`, `RETIRED`, `ENTERED_IN_ERROR`), with `VoltageYardRestoreParentNotActiveError`. The rule is expressed against the shared reference-data flag rather than a hardcoded list of codes or ids, so it stays correct if the status catalogue changes.
- **Governance lives in the service layer**, so both the existing `PATCH /voltage-yards/{id}` and the new dedicated `POST /voltage-yards/{id}/restore` funnel through the same check. No API client can bypass the allow-list by submitting an arbitrary `operational_status_id`.
- **The reference-protection rule is unchanged**: a yard still cannot be marked Entered in Error while an active Circuit/Transformer terminal references it, and a new terminal still cannot be created against an entered-in-error yard.

## Rationale

**Restoration preserves history; it does not undo it.** Restoring is an ordinary forward lifecycle transition that *appends* a new `substation_voltage_yard_audit_log` row (`ENTERED_IN_ERROR → ACTIVE`, with actor, timestamp and reason). The original correction entry is never modified or removed, so the permanent record shows both the correction and its reversal — exactly the discipline CLAUDE.md §5.2 requires. This is categorically different from a delete or an "undelete": nothing is erased, and no hard delete is introduced (§11.6 intact).

**A closed two-edge allow-list is stricter than what exists today, not looser.** Before this ADR any status could follow any other. After it, only two transitions are legal for a Voltage Yard. The restoration edge is therefore added *while* the overall lifecycle is being tightened — the net effect is more governance, not less.

**The exception is justified by identity, and is scoped to identity.** `ENTERED_IN_ERROR` remains terminal wherever a corrected record can be superseded by a newly-created one under a different identity. It is non-terminal only for Voltage Yards, and only because their identity is structurally non-reproducible while the uniqueness rule is status-blind. That is a property of the Voltage Yard entity, not a general softening of the status.

**Requiring a reason in both directions keeps the audit trail self-explanatory.** A reviewer reading the log sees why the yard was corrected and why the correction was reversed, without needing external context.

## Consequences

**Positive.** An accidental correction is recoverable through a controlled, audited, permission-gated action instead of being permanent. The previously unguarded status field is now governed by a closed allow-list, closing a real governance gap. The `(substation_id, voltage_level_id)` identity rule and its uniqueness constraint are untouched.

**Negative / accepted.** `ENTERED_IN_ERROR` is no longer universally terminal across GridDefence — a reader must now know that Voltage Yards are the single, documented exception. This ADR, the Deletion/Correction Policy section, and the ADR-008 addendum all state the exception explicitly so it is discoverable from any of the three places an engineer is likely to start. The reference-data `is_terminal` flag remains `true` for `ENTERED_IN_ERROR`: the flag describes the status's *default* semantics across the platform, and per-entity allow-lists remain the authoritative statement of legality — consistent with how substation transitions were already expressed (ADR-014), where the allow-list, not the flag, is enforced.

## Alternatives Considered

**Enforce terminality for Voltage Yards with no restoration path (rejected).** Consistent with every other entity, but it makes an accidental correction permanent and irreversible: the yard cannot be restored *and* cannot be replaced, so GridDefence could never again record a switchyard that physically exists. Locking the registry into a known-false state to preserve a uniform status semantic is precisely the trade CLAUDE.md §4 rejects.

**Exclude `ENTERED_IN_ERROR` rows from the uniqueness scope so a replacement yard can be created (rejected).** This would require replacing the table-level `UniqueConstraint` with a partial unique index (a schema migration) and would break ADR-008's stated invariant that a substation has at most one yard per voltage level — leaving two rows describing the same physical switchyard, one of them a tombstone. It also leaves the original governance gap unaddressed. Restoration achieves the same engineering outcome with no schema change and one fewer row.

**A general operational-status editor for Voltage Yards (rejected).** Exposing a free-form status dropdown would re-introduce exactly the arbitrary-transition problem this ADR closes, and would invite statuses (`MOTHBALLED`, `RETIRED`) that carry no defined meaning for a switchyard. The two lifecycle actions are deliberately expressed as two explicit, mutually exclusive commands.

**Recover the pre-error status from audit history (rejected).** Yards are only ever created `ACTIVE`, so history parsing would add a dependency on log completeness and a new failure mode to reproduce a value already known to be `ACTIVE`. Determinism was preferred; the history remains available for explanation.
