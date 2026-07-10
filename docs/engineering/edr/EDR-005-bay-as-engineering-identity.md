# EDR-005: Bay Is the Primary Engineering Identity — Already Satisfied by `CircuitTerminal` / `TransformerTerminal`

- **Status:** Accepted
- **Governing document:** [02-engineering-concepts.md](../02-engineering-concepts.md) — Bay; [04-domain-model.md](../04-domain-model.md) §1 (Central Relationship Chain)
- **Related:** [08-engineering-terminology.md](../08-engineering-terminology.md); `docs/architecture/equipment-registry-module.md` §7.5–§7.7; `docs/architecture/network-model-module.md` §19; ADR-007 (Canonical Engineering Reference Object); ADR-008 (Substation Voltage Yard)

> **Status update (post-ADR-011).** Every reference below to a "still-unbuilt" or "future" Relay Registry describes the state of the project at the time this EDR was accepted. That registry is now built, as the **Automatic Load Shedding Functionality Registry** — see [ADR-011](../../adr/ADR-011-automatic-load-shedding-functionality-registry.md) and `docs/architecture/automatic-load-shedding-functionality-registry-module.md`. It attaches to `CircuitTerminal`/`TransformerTerminal` exactly as this EDR's Decision anticipated — no part of this EDR's reasoning needed to change; this note only updates which references below are historical rather than current. The text below is left as originally accepted, per this project's practice of not rewriting past decisions as though they were always known.

---

## Background

A Phase 5 architecture verification examined how a substation is actually organized, independent of any one module's implementation, and reached the following engineering conclusion:

```
Substation
    │
contains
    │
    Bay
    │
hosts
    │
Primary Equipment
    │
operated by
    │
Breaker
    │
controlled by
    │
Relay / IED
```

A **Bay** is a fixed structural position at a substation — a breaker, its isolators, and its protection wiring — that hosts one piece of Primary Equipment (a transformer or a transmission line). Primary equipment may be replaced, upgraded, or re-terminated over the operational life of a substation; the Bay itself, and its relationship to the substation, normally persists throughout.

This matters because Grid Defence assignments, Relay Registry capability records, and PSS®E topology correlation all need a stable identity to attach to. If that identity were the *equipment* rather than the *bay*, replacing a transformer would silently break every reference to it — a scheme assignment, a capability record, a topology correlation — even though nothing about the substation's actual switching arrangement changed.

The question this decision resolves: does GridDefence's implementation need a new, generic `Bay` entity to provide this stable identity, or does an existing entity already provide it?

## Decision

**Bay is confirmed as the primary engineering identity a Shedding Action, a Relay Registry entry, and a PSS®E topology correlation all ultimately reference. No new, generic `Bay` database entity is introduced. The existing implementation already satisfies this requirement:**

- **Line Bay is `CircuitTerminal`** (Equipment Registry) — one substation's own terminal of a `Circuit`, with its own stable identity (`circuit_terminal_id`), independent of the `Circuit` (Primary Equipment) it currently belongs to.
- **Transformer Bay is `TransformerTerminal`** (Equipment Registry) — one side (HV or LV) of a `Transformer`, with its own stable identity (`transformer_terminal_id`), structurally identical in kind to `CircuitTerminal`.

This is a naming and documentation decision, not an implementation change: both entities already exist, in production, exactly as described.

## Rationale

**The evidence that these entities already are Bays, not just equipment records, was already in the codebase before this decision.** `CircuitTerminal` already has its own persistent identity independent of `Circuit`, its own `breaker_number`, its own commissioning date, and its own audit trail — everything the engineering concept of a Bay requires. `TransformerTerminal` mirrors this exactly for transformers. Neither is a bare foreign-key row; both are already first-class, independently-referenced objects (ADR-007 §6–§8).

**A real consumer already references them at exactly this granularity.** PSS®E Integration's `EquipmentTopologyMap` (Phase 4, already built) correlates PSS®E topology elements against `CircuitTerminal` specifically, per-terminal — i.e., against the Line Bay, not the `Circuit` as a whole. `equipment-registry-module.md` §7.7 already states the same principle for the still-unbuilt Relay Registry: *"A relay is physically wired to one substation's own breaker — never to a circuit as an abstract whole."* This decision does not invent a new rule; it names, formally, a rule the implementation was already following.

**Building a generic `Bay`/`Equipment` backbone now would be premature abstraction.** `equipment_registry/models.py`'s own header comment already records this reasoning: a shared polymorphic backbone was considered and deliberately deferred at both Phase 3 (Circuit/CircuitTerminal) and Phase 3.5 (Transformer/TransformerTerminal), because a backbone with only one or two real consumers would be structure built ahead of need (CLAUDE.md §21). Introducing one now, purely to have something literally named `Bay`, would repeat exactly the mistake that reasoning already avoided — for a purely terminological reason, not an engineering one.

**Primary Equipment replacement without Bay identity change is already possible.** Because `CircuitTerminal`/`TransformerTerminal` carry their own identity, a transformer replacement or a line re-termination is a data correction to the terminal's own reference fields, not a delete-and-recreate of the terminal itself. The engineering property this decision is meant to guarantee — Bay identity survives Primary Equipment change — already holds today.

**The only real gap was vocabulary, not structure.** Before this decision, nothing in `docs/engineering/` stated that `CircuitTerminal` and `TransformerTerminal` *are* Bays. An engineer or an AI coding agent reasoning from the engineering concept alone, without already knowing this codebase's history, could not have found the answer — and might have been tempted to design a new, redundant `Bay` entity to fill what looked like a missing piece.

## Consequences

**Positive:**
- No schema change, no migration, and no backend or frontend refactor is required — this decision closes a genuine open question with zero implementation cost.
- Future Relay Registry design can proceed directly against `CircuitTerminal`/`TransformerTerminal` as its Bay-level reference target, exactly mirroring `EquipmentTopologyMap`'s already-proven pattern, without first needing its own architecture debate about what a "Bay" is.
- Future Scheme-assignment design (UFLS/UVLS/EMLS migrating toward equipment-level assignment, per ADR-007 §12 item 7) has a settled answer for what a Transformer Bay Shedding / Line Bay Shedding action references.
- `docs/engineering/08-engineering-terminology.md` now records this mapping once, authoritatively, so it does not need to be rediscovered again.

**Negative / trade-offs:**
- `TransformerBay`'s current read-model granularity in Phase 5's Network Model (`backend/app/modules/network_model/schemas.py`) — one DTO per `Transformer`, combining HV and LV side data into a single row — is a display convenience and is coarser than the Bay-level granularity this decision confirms (`TransformerTerminal`, one per side). This does not need correction for Phase 5's own read-only, engineering-relationship purpose, but a future Relay Registry or Scheme-assignment module reaching for "the Transformer Bay" must be pointed at `TransformerTerminal`, not at Phase 5's `TransformerBay` DTO or at `Transformer` itself — this should be stated explicitly when that module's architecture is designed, not assumed.
- The word "Bay" still does not appear literally in the Equipment Registry's schema or code. This is an accepted, deliberate trade-off (see Rationale) — a future contributor unfamiliar with this EDR could still be confused without being pointed to it; [08-engineering-terminology.md](../08-engineering-terminology.md) and this record together are the mitigation, not a schema change.
