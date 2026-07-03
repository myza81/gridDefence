# ADR-005: Substation Operational Status Lifecycle

- **Status:** Accepted
- **Date:** 2026-07-03
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.3, §5.5, §8, A5)
- **Depends on:** none (Substation Registry is foundational Master Data — [ADR-002](ADR-002-identity-and-access-management.md) only supplies the accountability FK, not the lifecycle itself)
- **Affects:** [docs/architecture/substation-registry.md](../architecture/substation-registry.md) §8 rule 7, §10
- **Informed by:** a gap found during Phase 2 implementation and explicitly flagged (not silently resolved) in that phase's final report, "Architectural issues encountered"

---

## Context

[substation-registry.md](../architecture/substation-registry.md) §6 seeds `operational_status` reference data with six rows: `PLANNED`, `UNDER_CONSTRUCTION`, `ACTIVE`, `MOTHBALLED`, `DECOMMISSIONED`, `RETIRED`. That seed data was implemented in Phase 1, before this ADR existed.

§10's original ("v1") CRUD Lifecycle diagram, however, only drew five of those six states — `Under Construction` had no incoming or outgoing edge anywhere in the diagram. The diagram also showed `Decommissioned` reachable only via `Mothballed`, never directly from `Active`. §8 rule 7's prose compounded the gap by referencing an "explicitly cancelled before commissioning" exception with no corresponding status or definition anywhere in the document.

CLAUDE.md §5.5 (Deterministic Behaviour) and §5.3 (Explicit Architecture — "hidden behaviour is discouraged") make this a real defect, not a cosmetic one: §10 itself states "Status change: validated against the state machine above; illegal transitions rejected at the service layer" — the state machine's incompleteness meant the service layer could not correctly implement that sentence. During Phase 2 implementation, this was resolved *conservatively and temporarily* by treating every transition not literally drawn in the v1 diagram as illegal (a closed allow-list), which made `Under Construction` permanently unreachable and forbade `Active → Decommissioned` directly — and was flagged explicitly in Phase 2's final report as needing this follow-up decision rather than being treated as settled.

## Decision

The operational status lifecycle is revised to the following seven-edge closed transition graph, and `Under Construction` is restored to active use as the state a substation occupies between being registered (`Planned`) and entering service (`Active`):

```
Planned → Under Construction → Active
Active → Mothballed → Active
Active → Decommissioned → Retired
Mothballed → Decommissioned
```

| From | To |
|---|---|
| `Planned` | `Under Construction` |
| `Under Construction` | `Active` |
| `Active` | `Mothballed` |
| `Mothballed` | `Active` |
| `Active` | `Decommissioned` |
| `Mothballed` | `Decommissioned` |
| `Decommissioned` | `Retired` |

No other transition is legal. In particular: `Planned → Active` is no longer a legal *transition* (it must pass through `Under Construction`); `Retired` has no outgoing edge; nothing transitions into or out of `Under Construction` except the two edges above.

**`Under Construction` is included because it reflects a real, already-modeled physical state** — a substation can be under physical construction for months, is not yet safe or complete to mark `Active`, and grid defence scheme planning legitimately needs to distinguish "registered on paper" (`Planned`) from "physically being built" (`Under Construction`) from "in service" (`Active`). The reference data already existed since Phase 1; this decision only makes it reachable and gives it defined transition semantics, rather than introducing new reference data.

**`Active → Decommissioned` is included as a direct edge because mothballing is not a mandatory precondition of decommissioning.** `Mothballed` represents a *temporary, intended-to-be-reactivated* state (per §10's own framing); a substation can also be decommissioned directly and permanently from `Active` (e.g. after a structural failure, a permanent replacement, or a planning decision made without an intervening mothball period) without the architecture forcing an artificial, meaningless intermediate step.

**Creation-time initial status is unaffected by this decision.** §10's existing rule — a new `Substation` row may be created directly as `Planned` or `Active` (the data-migration/backfill case) — is a *creation-time exception*, not a transition, and remains exactly as documented. A substation created directly as `Active` does not retroactively pass through `Under Construction`.

**No `Cancelled` status is introduced.** §8 rule 7's old "unless explicitly cancelled before commissioning" phrase is removed rather than resolved by adding a new status, since no such status was ever seeded and no concrete requirement for it has been identified. If a genuine "planning cancelled" concept becomes a real requirement, it should be scoped in its own ADR — not retrofitted here as a side effect of closing this gap.

## Consequences

**Positive:**
- §10's own claim ("illegal transitions rejected at the service layer") is now actually true — the state machine is complete and every edge is enumerated.
- `Under Construction` reference data (seeded since Phase 1) is no longer permanently dead/unreachable data.
- Matches real-world substation commissioning practice: registered → under construction → in service, without forcing every decommissioning to go through an artificial mothball step.
- Resolves the specific gap Phase 2's final report flagged, closing the loop it explicitly left open rather than letting it silently persist into Phase 3 (Equipment Registry), which will itself reference `substation_id` and implicitly assume the substation lifecycle is stable and correct.

**Negative / trade-offs:**
- `Planned → Active` directly is no longer legal, which is a **behavioural change** from Phase 2's interim (already-shipped, but explicitly caveated as provisional) implementation. Any data created during Phase 2 that relied on that direct transition is unaffected retroactively (already-`Active` rows are not revalidated), but the transition itself is no longer offered going forward.
- Adds one more state engineers must understand and correctly select during data entry (`Planned` vs `Under Construction` vs `Active`), a minor data-entry burden in exchange for lifecycle accuracy.

---

## Alternatives Considered

1. **Seven-edge graph exactly as decided above.** **Adopted.** Uses reference data that already exists, matches real commissioning practice, and closes the exact gap Phase 2 flagged without introducing new reference data or new architectural concepts.

2. **Leave `Under Construction` permanently unreachable (keep Phase 2's conservative interim allow-list as final).** **Rejected.** This was always documented as a temporary, conservative placeholder pending this decision, not a considered design — leaving it as final would mean shipping reference data with no way to ever use it, which is itself a form of the "hidden/inconsistent behaviour" CLAUDE.md §5.3 discourages.

3. **Require `Active → Decommissioned` to always pass through `Mothballed`.** **Rejected.** This forces every decommissioning through a state (`Mothballed`) whose own definition ("temporary... reactivate") does not semantically apply to a substation being permanently retired — e.g. after a structural failure. Modeling reality accurately outweighs the minor simplification of having one fewer edge.

4. **Add a `Cancelled` status to resolve §8 rule 7's dangling "explicitly cancelled before commissioning" reference.** **Rejected for now.** No concrete requirement for a distinct cancelled-before-commissioning state has been identified; inventing reference data and transition rules to justify a stray phrase in prose is solving a problem that has not been shown to exist. The phrase is removed instead. Revisit via a dedicated ADR if a real requirement emerges.
