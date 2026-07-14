# UVLS Engineering Philosophy

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md). Read [scheme-engineering-principles.md](scheme-engineering-principles.md) and [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md) first — this document states only what is genuinely specific to UVLS.

Supersedes, in part, [uvls-module.md](uvls-module.md) §7–§8 (status note, not a rewrite). [`uvls-module.md`](uvls-module.md) §1–§6, §9 (minus lifecycle rules), §10–§18 remain authoritative for UVLS's ownership, non-responsibilities, referenced entities, Rule 3/4-equivalents, and testing priorities — most importantly §7.1's shared-vs-different comparison table against UFLS, which remains accurate in kind (only the lifecycle and Stage Setting Set *mechanism* changed, not the engineering distinctions it describes).

---

## 1. Voltage-Triggered Staged Philosophy

Voltage, unlike frequency, is fundamentally local — a voltage sag reflects a reactive-power deficiency concentrated in a specific area of the grid, not a uniform system-wide condition ([`uvls-module.md`](uvls-module.md) §1, unaffected). UVLS's stage design must reflect this locality directly, not force voltage thresholds into UFLS's system-wide shape.

## 2. Stage Setting Set Usage

UVLS uses its own Stage Setting Set ([stage-setting-set-architecture.md](stage-setting-set-architecture.md)), scoped to `scheme_type = UVLS`, never shared with UFLS. Each `StageSetting` within a UVLS Stage Setting Set carries an optional `region_scope_id` (Core Platform `region` reference data, read-only) — if set, the stage's threshold and assignments apply only within that region; if null, the stage applies grid-wide. Threshold ordering (strictly decreasing as `stage_order` increases) applies **within the same region scope only** — stages in different regions are never compared against each other. This is unchanged in substance from [`uvls-module.md`](uvls-module.md) §7.2/§9 rule 4, now expressed against the Stage Setting Set rather than the Scheme Version directly.

## 3. Per-Unit Voltage Thresholds and Delay

Unchanged from [`uvls-module.md`](uvls-module.md) §7.2: each stage setting carries `voltage_threshold_pu` — bus voltage expressed per-unit relative to the substation's own nominal voltage, normalizing across Substation Registry's diverse voltage classes. Time delay (`time_delay_ms`) is structurally identical to UFLS's own — the coordination-margin rationale applies equally to a voltage transient as to a frequency transient.

**Do not hardcode the present three stages.** Stage count and settings are driven entirely by the selected Published UVLS Stage Setting Set.

## 4. ALSF Relevance

Directly relevant, symmetric to UFLS ([ufls-engineering-philosophy.md](ufls-engineering-philosophy.md) §4) — the same non-removal-on-absence principle applies (a Critical finding, never an automatic removal from candidacy), using the UVLS-specific capability check rather than UFLS's. As with UFLS, this applies to every selected direct `TransformerTerminal` assignment and every selected boundary `CircuitTerminal` opening point alike, checked by UVLS's own assignment-validation logic — never by [boundary-pocket-architecture.md](boundary-pocket-architecture.md)'s own topology-only evaluation ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)). ALSF equipment inside a derived isolated island, as opposed to on a selected opening point, is irrelevant to boundary formation ([scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md) §3).

## 5. Transformer Terminal and Boundary Assignments

Direct assignment is UVLS's primary and dominant mechanism — a direct, substation-by-substation reduction of load in the voltage-deficient zone is the natural engineering response to a local problem. **Boundary Pocket assignment remains available but is expected to be rare** ([`uvls-module.md`](uvls-module.md) §7.4's reasoning, unaffected by [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md)): electrical isolation can worsen, not help, a local voltage deficiency if the isolated pocket is cut off from external transmission paths that were supplying it reactive-power support. Narrow genuine exceptions (a weak radial sub-transmission configuration where isolation is a deliberate, engineered response) are why the mechanism remains available, never removed.

## 6. Location/Topology Sensitivity

UVLS additionally consults live bus voltage magnitude from the current evaluation snapshot during candidate review — directly informing which substations belong in a given region-scoped stage, distinct from UFLS's own recommendation surface, which has no per-bus quantity worth querying individually ([`uvls-module.md`](uvls-module.md) §7.5, unaffected).

## 7. Target MW and Current Evaluation

Standard, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) — the shared ±10% global tolerance, unless a future UVLS-specific override is administratively configured.

## 8. Publication and Continuous Evaluation

Standard, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) — no UVLS-specific deviation, beyond the region-scoped Stage Setting Set completeness check inherited from §2.
