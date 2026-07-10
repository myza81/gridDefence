# ADR-011: Automatic Load Shedding Functionality Registry — Retiring "Relay Registry" for a Precisely-Scoped, Dedicated Module

- **Status:** Accepted
- **Date:** 2026-07-09
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1, §8, §11.2, §11.8, §20, A1, A2, A5, A8)
- **Depends on:** [ADR-006](ADR-006-connectivity-registry-vs-psse-topology-architecture.md), [ADR-007](ADR-007-canonical-engineering-reference-object.md), [ADR-008](ADR-008-substation-voltage-yard.md)
- **Related:** [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md) (Relay Registry scope — the engineering concept this ADR gives a final bounded-context home to), [EDR-005](../engineering/edr/EDR-005-bay-as-engineering-identity.md) (Bay as engineering identity — the attachment point this module references), [docs/architecture/equipment-registry-module.md](../architecture/equipment-registry-module.md) §7.8 (superseded by this ADR — see §3 below), [docs/architecture/critical-infrastructure-module.md](../architecture/critical-infrastructure-module.md) (the structural precedent this ADR follows)
- **Supersedes (in part):** [ADR-007](ADR-007-canonical-engineering-reference-object.md) §2, §10 — specifically the statement "no separate Relay Registry module exists or is proposed." ADR-007's conclusions about `Circuit`/`CircuitTerminal` as the canonical engineering reference object, and about Equipment Registry's own boundaries, are **unaffected** and remain authoritative.

---

## 1. Context

[ADR-007](ADR-007-canonical-engineering-reference-object.md) evaluated a *general-purpose relay wiring* concern — a physical relay's identity and which piece of equipment it physically trips — and decided it belongs inside Equipment Registry as a Master Data extension (`RelayDetail`/`RelayControlledEquipment`, `equipment-registry-module.md` §7.8), explicitly rejecting a separate module. That design was never built: `implementation-plan.md`'s Phase 3 status note confirms "no generic `Equipment` backbone and no `RelayDetail`/`RelayControlledEquipment` were built — both remain deliberately deferred future scope." The as-built Equipment Registry has no generic `Equipment` table at all; §7.8's design assumed a backbone that does not exist in the delivered schema.

Independently, [EDR-003](../engineering/edr/EDR-003-relay-registry-scope.md) (Engineering Reference Library, Accepted) had already scoped a narrower engineering question: *"can this bay or switching point be operated by a Grid Defence Scheme?"* — deliberately not a relay asset-management concern. `02-engineering-concepts.md` and `glossary.md` both list "Relay Registry" as one of five parallel Engineering Knowledge (Layer 1) registries, alongside — not inside — Equipment Registry.

Engineering review of this question (this session's own prior architecture review) found these two framings only partially reconciled, and recommended keeping relay capability inside Equipment Registry as a revision of §7.8 plus a derived capability-query interface.

**That recommendation is now superseded by a sharper, confirmed engineering specification.** The concept has been refined from "general relay wiring" to something materially narrower and more specific:

- It answers exactly two questions, per Bay Terminal: is automatic UFLS functionality installed/wired/configured/commissioned/available, and is automatic UVLS functionality likewise available — **not** a generic "can this relay trip something" fact.
- **EMLS is explicitly excluded** — EMLS is manually invoked and may be assigned to any bay at the designer's discretion, so it has no automatic-functionality prerequisite at all. This exclusion is itself scheme-shape-aware in a way general relay wiring never was.
- The record carries its **own independent lifecycle** (added → activated → deactivated → decommissioned/dismantled) and its own full audit history, distinct from the underlying terminal's own equipment lifecycle.
- It must support a **candidate-search** query shape ("which bays are available for UFLS/UVLS assignment") that is designed, from the outset, to compose with future UFLS/UVLS scheme data — a cross-cutting, scheme-shedding-aware read pattern.
- Relay make/model are explicitly **secondary, optional metadata**, not the registry's subject matter — reinforcing, more strongly than ADR-007's general framing did, that this is not an asset-management concern.

This is no longer "relay wiring, generically" — it is a scheme-shedding-specific functionality record. Equipment Registry's own architecture document is explicit that it has "no knowledge of 'schemes,' 'stages,' or 'shedding assignments'" (§4, §9 rule 10) and exists to answer "what equipment and circuits exist, where, and how are they identified and wired" — not "is this bay functionally ready for a specific class of automatic scheme execution." A registry whose core columns are literally named `ufls_function`/`uvls_function` sits on the wrong side of that boundary if placed inside Equipment Registry.

## 2. Decision

**"Relay Registry" is retired as a working name and as a design direction inside Equipment Registry.** In its place, GridDefence establishes the **Automatic Load Shedding Functionality Registry** as a new, dedicated bounded context within the Engineering Registry domain grouping — structurally the same pattern already used for Critical Infrastructure (`critical-infrastructure-module.md`): its own tables, its own service layer, its own audit trail, referencing Equipment Registry's `CircuitTerminal`/`TransformerTerminal` read-only, by ID, never duplicating their attributes.

This module:

- Owns exactly one entity family: the automatic-shedding-functionality status of a Bay Terminal, per the schema outlined in `automatic-load-shedding-functionality-registry-module.md` (new document, this ADR's companion).
- Has no knowledge of UFLS/UVLS scheme versions, stages, or assignments. It answers "is this terminal functionally ready," never "is this terminal currently assigned." Assignment status is composed, read-only, by UFLS/UVLS themselves once those modules exist (mirroring exactly how Critical Infrastructure supplies data to Cross-Scheme Compliance without ever deciding compliance itself).
- References `CircuitTerminal` for line/circuit bay disconnection points and `TransformerTerminal` for transformer bay disconnection points — the same Bay attachment points EDR-005 already established, via a two-way, database-enforced XOR (mirroring the existing precedent already used in this codebase: `LoadSnapshotElementState`'s `ck_load_snapshot_element_state_xor` and `EquipmentTopologyMap`'s `ck_equipment_topology_map_target_xor`, both in `psse_integration/models.py`).

`equipment-registry-module.md` §7.8 ("Relay Model — The Relay Ownership Decision") is superseded by this ADR. Per this project's established documentation practice (`equipment-registry-module.md`'s own header: "correcting the authoritative text directly while noting supersession rather than rewriting every narrative example"), §7.8 is annotated as superseded, pointing here, rather than deleted or silently rewritten.

## 3. Rationale

**A registry whose schema names two specific schemes is a scheme-shedding-aware concern, not a generic equipment-wiring concern.** ADR-007's placement of general relay wiring inside Equipment Registry rested on relay wiring being physical Master Data "no different in kind from a transformer's physical existence" — true for *generic* relay/tripping wiring, but no longer true once the concept's own schema encodes `ufls_function`/`uvls_function` directly. That is functionally adjacent to Critical Infrastructure's `restriction_type`, not to `Transformer`'s `capacity_mva`.

**This mirrors the precedent this codebase has already set once.** The prior architecture review reached the same conclusion for Sensitive Customer Registry by direct analogy to Critical Infrastructure — a substation-referenced classification/restriction registry, deliberately kept separate from both Substation Registry and Equipment Registry despite being "conceptually simple," specifically to preserve each registry's narrow, trustworthy scope (EDR-003's own stated discipline: "each registry is scoped to the specific engineering question the platform actually needs answered"). Folding this registry into Equipment Registry for expediency would repeat the exact risk that precedent was set to avoid.

**Independent lifecycle and audit history are a structural signal, not an incidental detail.** Every entity in Equipment Registry today (`Circuit`, `CircuitTerminal`, `Transformer`, `SubstationVoltageYard`) uses the current-state-plus-audit-log pattern *for the equipment's own existence*. This registry's lifecycle (added/activated/deactivated/decommissioned) tracks a *different* fact — the functionality's own readiness state — which can change independently of the terminal's own equipment lifecycle (a terminal can remain fully commissioned equipment while its automatic shedding functionality is deactivated for maintenance, or vice versa). Two independently-changing lifecycles attached to the same object are a signal of two distinct owned facts, not one.

**Candidate search is a cross-cutting read pattern this registry must be designed for from day one**, anticipating composition with UFLS/UVLS data that does not yet exist. Equipment Registry's own architecture deliberately never grows a "candidate for scheme X" query shape (§4: no knowledge of schemes) — building one there would be the first crack in a boundary that has otherwise held cleanly across every module in this series.

**The as-built gap makes this a clean, costless correction, not a rework.** Because `RelayDetail`/`RelayControlledEquipment` (ADR-007 §7.8) were never implemented, there is no code, no migrated data, and no live consumer to reconcile — this ADR changes a still-unbuilt design, at zero implementation cost, exactly the situation ADR-007 itself was written to take advantage of ("This ADR exists to foreclose that outcome before Phase 3 implementation begins, while there is still no code or migrated data to reconcile" — the same condition holds here, one module later).

## 4. Consequences

**Positive:**
- A precisely-named, precisely-scoped registry that matches the confirmed engineering specification exactly, rather than a broader relay-asset concept stretched to fit.
- Equipment Registry's boundary (no knowledge of schemes) remains fully intact — this was at real risk of erosion had `ufls_function`/`uvls_function` been added there.
- Follows an already-proven structural precedent (Critical Infrastructure) rather than inventing a new pattern, minimizing architectural surface area (CLAUDE.md §21).
- UFLS and UVLS both consume this registry identically (it makes no distinction in ownership between the two scheme types, only in its two boolean facts) — a clean, symmetric dependency for both future modules.

**Negative / trade-offs:**
- One more bounded context in the Engineering Registry domain grouping (now: Substation Registry, Equipment Registry, this module, and — pending its own ADR — Sensitive Customer Registry) — a modest increase in the number of modules a new engineer must learn, accepted as the cost of keeping each one narrowly trustworthy (EDR-003's own trade-off, restated).
- `equipment-registry-module.md` §7.8 now reads as a superseded, historical section rather than the live design — readers of that document must follow the supersession note to find the authoritative model, the same navigation cost already accepted elsewhere in this series (e.g. the connectivity validation document's own relationship to ADR-007).
- The `CircuitTerminal`/`TransformerTerminal` reference this module holds is read-only and by ID only; if either underlying terminal is ever deleted or re-typed, this module's own row becomes an orphaned-reference concern this module's service layer — not Equipment Registry's — must handle gracefully (see the companion module document's Validation Rules).

## 5. Alternatives Considered

- **Extend Equipment Registry directly** (add `ufls_function`/`uvls_function` columns, or a sibling detail table, inside Equipment Registry). Rejected per §3 above — this is the option the engineering review already flagged as risking scope creep into scheme-shedding-specific territory Equipment Registry's own document explicitly disclaims.
- **Revive and build ADR-007 §7.8's general relay model as originally designed, then layer UFLS/UVLS-specific flags on top of it.** Rejected: adds a layer of indirection (generic relay wiring → derived capability) the confirmed specification doesn't need, and reintroduces exactly the "which equipment does this relay trip" framing EDR-003 already warned against drifting toward being asset-management in disguise.
- **Fold this into a future, single "Grid Defence Capability" registry covering EMLS too.** Rejected: EMLS has no automatic-functionality prerequisite by design (manual, assignable to any bay) — forcing a uniform three-scheme model onto a concept that is structurally two-scheme-only would misrepresent EMLS's own engineering reality for no benefit.

## 6. Decision Record

This ADR authorizes the new module document `docs/architecture/automatic-load-shedding-functionality-registry-module.md` (companion to this ADR) as the authoritative design for the Automatic Load Shedding Functionality Registry. It authorizes the corresponding updates to `domain-model.md`, `system-overview.md`, `08-engineering-terminology.md`, and the supersession annotation in `equipment-registry-module.md` §7.8, all prepared alongside this ADR.

No implementation begins from this ADR alone — per CLAUDE.md §24, architecture precedes implementation, and this ADR is the architecture layer's own output, not an implementation instruction.
