# ADR-022: Continuous Evaluation Detector Framework

- **Status:** Accepted
- **Date:** 2026-07-15
- **Implementation status (Shared Platform Sprint 5, 2026-07-16):** The `EngineeringFindingDetector` interface, explicit static `DetectorRegistry`, and the synchronous Continuous Evaluation Engine core (`backend/app/modules/continuous_evaluation/`) are implemented exactly as this ADR specifies, along with the first and, so far, only registered detector (MW tolerance deviation). No dynamic discovery mechanism was introduced. ADR-023's own background/event-driven refresh path remains unimplemented; no other detector (ALSF, Sensitive Customer, topology/registry change, Boundary Pocket, cross-scheme overlap, Critical Infrastructure) is implemented yet.
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§21, A1, A6)
- **Depends on:** [ADR-018](ADR-018-findings-severity-and-publication-governance-separation.md) (this ADR decides *how detectors are structured in code*; it does not revisit ADR-018's own decision that severity and treatment are separate axes, or the `Finding` shape ADR-018 already defines)
- **Affects:** [docs/architecture/continuous-evaluation-architecture.md](../architecture/continuous-evaluation-architecture.md) (gains a new §3.3 — see Consequences), [docs/architecture/findings-and-publication-governance-architecture.md](../architecture/findings-and-publication-governance-architecture.md) §11 (`evaluateFindings`'s own internal fan-out mechanism is now specified, not left implicit)
- **Informed by:** the Shared Defence-Scheme Platform Implementation Readiness Review; ADR-018's own flagged risk ("a future implementer could easily reintroduce a bespoke gating shortcut inside one specific detector by habit")

---

## Context

`findings-and-publication-governance-architecture.md` §3 lists seven finding sources today (MW tolerance, ALSF, Sensitive Customer, topology/registry change, Boundary Pocket structural, Boundary Pocket composition, cross-scheme overlap, critical-infrastructure protection — eight, by exact count) and `scheme-future-extensibility.md` §1 anticipates more arriving with every future scheme type (SPS, RAS, generator rejection, controlled islanding). `evaluateFindings(scheme_version_id, evaluation_snapshot) → Finding[]` is specified as "the shared entry point... fanning out internally to every applicable detector" ([findings-and-publication-governance-architecture.md](../architecture/findings-and-publication-governance-architecture.md) §11), but the *shape* of that fan-out — one growing method with a detector's worth of logic inlined per finding type, or a set of independently-implemented, registered components — is not decided anywhere in the pack.

This is exactly the shape of decision ADR-018's own Consequences section already flagged as a risk: "a future implementer could easily reintroduce a bespoke gating shortcut inside one specific detector by habit." Left undecided, the natural path under implementation pressure is one large `evaluateFindings` method growing an `if scheme_type == ...` branch per new finding type — the antithesis of what `scheme-future-extensibility.md` §10 requires ("a new scheme type uses shared platform capabilities... wherever the underlying engineering problem is genuinely the same shape").

## Decision

**Detectors are independent, registered components — never hardcoded branches inside one evaluation method.**

### Detector interface

```text
EngineeringFindingDetector:
    detector_id: str                    # stable, unique — e.g. "mw_tolerance",
                                         # "boundary_pocket_structural", "alsf_capability"
    applicable_scheme_types: set[str]   # e.g. {"UFLS", "UVLS"}, or {"*"} for every scheme type

    detect(context: EvaluationContext) -> list[Finding]
```

- `detector_id` becomes `Finding.source` (ADR-018's own field) — the identity `PublicationTreatmentPolicy` keys treatment resolution against. Stable once shipped, per ADR-018 §9's own "a `Permission`'s meaning is immutable once registered" precedent applied here to detector identity.
- `applicable_scheme_types` lets the same registered detector set serve every scheme type without a scheme module needing to know which detectors apply to it — the Evaluation Engine filters by scheme type before invoking, not the scheme module and not the detector's own caller.
- Every detector receives the same `EvaluationContext` shape (scheme_version_id, scheme_type, evaluation snapshot identity, the calling scheme module's own resolved assignment universe — passed in by the caller, never queried by the detector directly from another module's tables, preserving CLAUDE.md A1) and returns `list[Finding]`, using exactly the `Finding` shape ADR-018 §2 already specifies. No detector defines its own result shape.
- A detector is a pure function of its `EvaluationContext` plus whatever read-only service-layer dependencies it is constructed with (e.g. the MW tolerance detector depends on Engineering Parameter Configuration's own read interface, per [ADR-021](ADR-021-engineering-parameter-configuration-ownership.md); the ALSF detector depends on the ALSF Registry's own service). Dependencies are supplied at construction (ordinary dependency injection, mirroring every existing service's own `__init__(self, db)` pattern in this codebase), never resolved by the detector reaching into another module's repository directly.

### Registration mechanism

**Explicit, static registration — not dynamic plugin discovery.** Each detector is registered by one call, at the Continuous Evaluation Engine's own bootstrap/composition point, mirroring the exact pattern every existing module already uses to register its own permission catalog entries in `bootstrap.py`:

```text
registry.register(MwToleranceDetector(engineering_parameters_service))
registry.register(AlsfCapabilityDetector(alsf_service))
registry.register(SensitiveCustomerDetector(sensitive_customer_service))
registry.register(BoundaryPocketStructuralDetector(network_model_service))
registry.register(BoundaryPocketCompositionDetector(network_model_service))
...
```

Dynamic discovery (filesystem scanning, entry-point/plugin metadata, a database-driven detector catalog) is deliberately rejected — this is an in-process modular monolith (CLAUDE.md §6), not a system with independently-deployed plugins; a compile-time-visible, explicitly-registered list is simpler, more auditable in code review, and equally sufficient for "add a detector without modifying `evaluateFindings`'s own loop" (CLAUDE.md §21 — do not build infrastructure a requirement does not actually need).

### Execution

`evaluateFindings(scheme_version_id, evaluation_snapshot)`:
1. resolves `scheme_type` and the calling scheme module's own current assignment universe (via that module's own service interface, per [shared-defence-scheme-domain-model.md](../architecture/shared-defence-scheme-domain-model.md) §8);
2. builds one `EvaluationContext`;
3. selects every registered detector whose `applicable_scheme_types` includes this `scheme_type` (or `"*"`);
4. invokes each selected detector's `detect(context)`, collecting every returned `Finding`;
5. returns the concatenated `Finding[]` — no detector's output depends on another detector's output.

**Execution order carries no meaning and is not guaranteed beyond registration order.** Every detector must be independent — a detector may never read another detector's result as an input. This is a hard constraint on any future detector, not merely today's default: a detector design that seems to need another detector's output first is a signal that the two are actually one detector, or that the dependency belongs in the shared `EvaluationContext` both need, not a detector-to-detector data flow. This independence is also what makes parallel execution (a future performance option, not built now — CLAUDE.md §21) available without redesign later.

### Future extensibility

A new detector — a future SPS-specific finding, a future generator-rejection check, Critical Infrastructure's own Rule-2-equivalent once that module exists — is: one new class implementing the interface above, plus one new `registry.register(...)` line at bootstrap. `evaluateFindings`'s own orchestration logic (steps 1–5 above) never changes. This is the concrete mechanism that satisfies `scheme-future-extensibility.md` §10's "new finding types, no redesign required" and directly closes the drift risk ADR-018 flagged.

## Rationale

**A registered-component model is the only shape that keeps `evaluateFindings` from becoming exactly the kind of duplicated, drifting logic ADR-018 already warned about for the governance layer, now for the detection layer too.** ADR-018 solved "every finding type needs the same severity/treatment separation, not a bespoke model per type" for *policy*. This ADR solves the identical problem one layer down, for *detection code structure* — without it, every new finding type would tempt a fresh `if`/`elif` branch inside one growing method, the precise anti-pattern `ufls-module.md` §17/§18 already flagged for Rule 7/8 validation logic drift, now scaled to eight-or-more branches instead of two.

**Static registration, not dynamic discovery, is the CLAUDE.md §21-correct choice for this codebase's actual deployment shape.** GridDefence is a modular monolith (CLAUDE.md §6), not a host for independently-shipped detector plugins; every detector this pack currently names, and every one `scheme-future-extensibility.md` anticipates, ships in the same codebase, in the same deployment, reviewed by the same process. Dynamic plugin infrastructure (entry points, filesystem scanning, runtime-loaded detector catalogs) would solve a problem this platform does not have, at the cost of exactly the kind of "premature optimisation... unnecessary abstraction" CLAUDE.md §21 warns against.

**Independence between detectors is what keeps the framework correct under both today's synchronous, on-demand evaluation path and tomorrow's potential parallel/async one**, without needing to decide execution order semantics now. Requiring it explicitly, as a constraint on every detector's own design rather than an accident of today's implementation, is what prevents a future detector from silently depending on ordering nobody guaranteed.

## Consequences

**Positive:**
- Closes ADR-018's own flagged risk concretely, in code structure, not only in policy.
- Every future finding source (per `scheme-future-extensibility.md` §1's own stress-test list) has one, obvious, already-proven extension point.
- Detector independence keeps testing simple — each detector is unit-testable in isolation, against a synthetic `EvaluationContext`, with no dependency on any other detector or on a real scheme module existing yet (directly enabling the Shared Platform's own sprint sequencing, which has no real scheme module to test against until Phase 6).

**Negative / trade-offs:**
- One additional small abstraction (the detector interface and registry) that a single-method implementation would not have needed — justified by the drift risk it closes, not introduced for its own sake.
- Every detector must resolve its own dependencies through service-layer calls, never direct repository access into another module — slightly more setup per detector than an inlined branch would need, the ordinary and already-accepted cost of CLAUDE.md A1 everywhere else in this codebase.

---

## Alternatives Considered

1. **Registered, independent detector components, as decided above.** **Adopted.** Directly closes ADR-018's own flagged drift risk; matches CLAUDE.md §21's "no more infrastructure than the requirement needs" for a modular monolith specifically.

2. **Hardcoded evaluation logic inside one `evaluateFindings` method, one branch per finding type.** **Rejected.** This is the status quo the readiness review flagged as a real risk, not a genuine alternative — it is exactly the shape ADR-018's Consequences already named as the failure mode to avoid, now formalized as explicitly rejected rather than left to happen by default.

3. **Dynamic plugin discovery (filesystem scanning, entry-point metadata, or a database-driven detector catalog).** **Rejected.** Solves a deployment-topology problem (independently-shipped plugins) this modular monolith does not have; adds infrastructure and indirection CLAUDE.md §21 does not justify given a compile-time-visible registration list already satisfies every stated extensibility requirement.
