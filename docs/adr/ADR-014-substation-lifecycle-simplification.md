# ADR-014: Substation Lifecycle Simplification

- **Status:** Accepted
- **Date:** 2026-07-11
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.3, §5.5, §8, A5, A13)
- **Supersedes:** [ADR-005](ADR-005-substation-operational-status-lifecycle.md) (Substation Operational Status Lifecycle) — the seven-edge, six-state graph ADR-005 defined is replaced by the four-state, four-edge graph below. ADR-005 itself is left unmodified as a historical record of the lifecycle's prior form; this ADR documents the change and supersedes it going forward.
- **Depends on:** none (Substation Registry is foundational Master Data)
- **Affects:** [docs/architecture/substation-registry.md](../architecture/substation-registry.md) §8 rule 7, §10
- **Informed by:** Project Owner instruction, "Substation Registry Enhancement — Lifecycle Simplification"

---

## Context

ADR-005 established a six-state Substation lifecycle (`Planned`, `Under Construction`, `Active`, `Mothballed`, `Decommissioned`, `Retired`) with seven legal transitions. The Project Owner subsequently determined this model is more granular than the engineering workflow actually requires, and directed that the Substation lifecycle be simplified to four states with a closed three-source-state transition graph, removing `Planned`, `Mothballed`, and `Retired`.

`operational_status` is Core Platform reference data shared across modules (`app/reference_data/seed.py`) — Equipment Registry's own service layer (Circuit, Transformer, SubstationVoltageYard) independently uses `Planned`, `Mothballed`, and `Retired` codes for its own, unrelated status model, entirely separate from the Substation lifecycle this ADR governs (CLAUDE.md module-ownership boundary — each module owns its own business rules over shared reference data). Removing these codes from the *reference table* would silently break Equipment Registry's own lifecycle, which is out of scope for a Substation Registry enhancement and would violate CLAUDE.md A1/§12 module-boundary discipline.

## Decision

The Substation lifecycle is narrowed to four states and the following closed, four-edge transition graph:

```
Under Construction → Active
Under Construction → Entered in Error
Active → Decommissioned
Active → Entered in Error
```

| From | To |
|---|---|
| `Under Construction` | `Active` |
| `Under Construction` | `Entered in Error` |
| `Active` | `Decommissioned` |
| `Active` | `Entered in Error` |

No other transition is legal. `Decommissioned` and `Entered in Error` are both terminal — neither has an outgoing edge.

**Engineering meaning of each retained state:**

- **`Active`** — the substation exists and is part of the current engineering network model; participates normally in engineering workflows.
- **`Under Construction`** — physically exists, construction has commenced; a valid engineering asset; not yet operational. It must appear in the Substation Registry, in engineering searches/registry views, and remain visible in dashboards/reports. It must **not** participate in downstream engineering workflows that require an operational substation (e.g. ALSF assignment, Sensitive Customer assignment, UFLS, UVLS, EMLS). No downstream module changes are made by this ADR — this is the lifecycle definition future modules must respect when they are built.
- **`Decommissioned`** — permanently existed but removed from service; retained only for engineering history.
- **`Entered in Error`** — the record should never have existed; retained only for audit purposes (mirrors the existing `ENTERED_IN_ERROR` correction pattern already used by Equipment Registry — CLAUDE.md §11.6).

**`Planned`, `Mothballed`, and `Retired` are removed from the Substation lifecycle**, not from the shared `operational_status` reference table. The underlying reference rows remain seeded (`app/reference_data/seed.py`'s `OPERATIONAL_STATUSES` list is unchanged) because Equipment Registry independently depends on them for Circuit/Transformer/SubstationVoltageYard status modeling. `SubstationService`'s own closed allow-list (`_STATUS_TRANSITIONS`, `_ALLOWED_INITIAL_STATUS_CODES`) simply no longer includes these three codes, so the service layer rejects them for a Substation exactly as it would reject any code outside the closed list — the removal is enforced entirely within Substation Registry's own module boundary, with zero change to Equipment Registry's behaviour.

**Creation-time initial status is `Under Construction` or `Active`.** `Under Construction` replaces the removed `Planned` as the "newly registered" entry point (a substation being registered ahead of or during construction); `Active` remains available directly for the historical/backfill data-entry case (registering a substation that has already been in service), unchanged in kind from ADR-005's own creation-time exception.

**Pre-existing Substation rows holding a removed status code are left untouched.** This ADR does not migrate, reassign, or otherwise alter any existing `Substation.operational_status_id` value — per CLAUDE.md §5.2 (Immutable Engineering History) and the same "do not invent or silently alter real data" discipline already applied when `gm_zone_id` was tightened to `NOT NULL` (migration 0016_gm_zone). A Substation left at a removed status (e.g. `Retired`) simply has no further legal transition available to it under the new closed list — `_STATUS_TRANSITIONS.get(current_code, set())` returns an empty set for any code no longer present as a key, which correctly and safely treats it as terminal without erroring or requiring a data migration. If the Project Owner later decides such rows must be reclassified, that is a separate, explicit data-correction decision, not an automatic side effect of this ADR.

## Consequences

**Positive:**
- The Substation lifecycle now matches the engineering workflow the Project Owner actually needs, with fewer states for data-entry staff to choose between.
- `Entered in Error` gives Substation Registry the same correction mechanism Equipment Registry already uses (CLAUDE.md §11.6), rather than only supporting historical retirement.
- No cross-module impact: Equipment Registry's own status model, which happens to share the same `operational_status` reference table, is completely unaffected.

**Negative / trade-offs:**
- `Mothballed` (temporary, intended-to-reactivate) is no longer expressible for a Substation — a substation taken out of service must go directly to `Decommissioned`, which is a permanent-record status. If a genuine "temporarily out of service, intended to return" requirement re-emerges, it should be scoped in its own ADR rather than reintroduced as a side effect of another change.
- `Retired` as a distinct post-`Decommissioned` administrative-closure step no longer exists — `Decommissioned` is now the sole terminal "no longer in service" state.
- Any pre-existing Substation left at a removed status code (`Planned`/`Mothballed`/`Retired`) becomes permanently terminal (no further status change possible) until a separate, explicit data-correction decision is made.

---

## Alternatives Considered

1. **Four-state, four-edge graph exactly as decided above.** **Adopted.** Matches the Project Owner's explicit instruction and keeps `Entered in Error` available as the correction mechanism, consistent with the pattern already established elsewhere in the codebase.

2. **Delete `Planned`/`Mothballed`/`Retired` rows from the shared `operational_status` reference table.** **Rejected.** Equipment Registry's own service layer independently uses these codes for Circuit/Transformer/SubstationVoltageYard; deleting the rows would silently break another module's business rules, violating CLAUDE.md's module-ownership boundary (A1) for a change scoped only to Substation Registry.

3. **Migrate/reassign any pre-existing Substation currently holding a removed status code to a new value.** **Rejected for now.** No such reassignment was requested, and inventing a target value would be exactly the kind of unauthorized data change CLAUDE.md §5.2 and this project's established "do not invent or silently alter real data" discipline prohibit. Left as an explicit follow-up decision if the Project Owner identifies a concrete need.
