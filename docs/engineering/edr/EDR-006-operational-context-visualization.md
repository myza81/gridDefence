# EDR-006: Operational Context Should Ultimately Be Visualized, Not Only Summarized in Text

- **Status:** Accepted
- **Governing document:** [01-engineering-philosophy.md](../01-engineering-philosophy.md) §2, §6 (Layer 2 — Operational Context), §9 (Role of Supporting Modules), §10 (Principles 1, 9, 10)
- **Related:** [03-system-workflow.md](../03-system-workflow.md); [04-domain-model.md](../04-domain-model.md); [07-future-roadmap.md](../07-future-roadmap.md) §3 (Heatmaps, Historical comparison); [EDR-001](EDR-001-psse-as-operational-context.md) (PSS®E as Operational Context, not engineering truth); [EDR-004](EDR-004-decision-support-not-automation.md) (decision support, not automation); `docs/architecture/psse-integration-module.md` §8.9b/§8.9d (the Preview and Import Result engineering presentation refinements this decision generalizes)

---

## Background

Phase 6 UAT reviewed the PSS/E Import Preview and Import Result pages from the perspective of practising Grid Defence engineers. Both pages were found to be technically correct, and both were refined (§8.9b, §8.9d) to present engineering information — snapshot type, network size, registry matching, engineering findings — in plain engineering language rather than raw implementation terms.

Even after that refinement, a further observation remained: textual summaries, however well-worded, do not give an engineer the same *situational awareness* of an uploaded network that a spatial view does. Transmission engineers reason about a network the way they were trained to — as a diagram of substations and lines — not as a table of counts and percentages. When reviewing a newly uploaded PSS®E snapshot, the questions an engineer asks first are inherently spatial: what kind of network is this, does it resemble the expected transmission system, what voltage levels are present, is it highly interconnected, are there isolated areas — questions a "Network Size" table answers in numbers, but a network view answers in one glance.

This is not a new engineering behaviour. It is a recognition that one of decision support's own existing tools — presentation — has a form (visual, spatial) that GridDefence has not yet used, alongside the form (textual, tabular) it already has.

## Decision

**Operational Context should ultimately be presented using engineering-oriented visualisation, in addition to textual summaries.**

Visualisation supports engineering understanding. It never replaces engineering judgement, and it never becomes a second source of engineering truth alongside the Registries, PSS/E Integration's own versioned data, or a Grid Defence Scheme. A visual network view is a *presentation* of Operational Context an engineer already has read access to — exactly as a textual summary already is — never a new computation, and never a new engineering fact.

## Rationale

**Transmission engineers naturally reason using network topology.** An engineer's mental model of "the network" is already a spatial one — substations, the lines between them, voltage levels, interconnection — before it is ever a list of numbers. Presenting Operational Context in the same form an engineer already thinks in reduces the translation effort between what the system shows and what the engineer needs to understand.

**A graphical overview communicates network structure significantly faster than tables or statistics.** "312 substations, 1,847 lines, 22% coverage" takes real effort to turn into "does this look like our grid." A spatial view answers that question almost immediately, precisely because it presents the same structure an engineer would sketch on a whiteboard.

**Visualisation helps engineers verify that an uploaded operational context is broadly consistent with expectations before accepting it.** This is squarely a Preview-time and Import-Result-time need (§8.9b, §8.9d): before a batch is activated and its data becomes Current, an engineer benefits from being able to see, not just read, that the uploaded snapshot looks like the transmission network they expect — the same "is this the operational snapshot I intend to import" question the Preview refinement was already built to answer in words.

**Visualisation supports engineering review; it does not perform engineering analysis.** A rendered network view may show which substations exist and how they connect, exactly as the underlying data already states. It must never compute or imply an engineering conclusion the data itself does not already contain — no highlighting of a "problem area" the system has decided is a problem, no inferred islanding, no derived risk score. The moment a visualisation computes something beyond what is already stored, it has stopped being a presentation and started being a second, ungoverned analysis capability — precisely what [EDR-004](EDR-004-decision-support-not-automation.md) already forecloses for every other GridDefence capability.

**Visualisation must remain a decision-support capability, not a decision-making one.** An engineer looks at a network view, forms a judgement, and acts — publishing a scheme, activating a batch, requesting a correction. The view itself never activates, never approves, never flags pass/fail. It is read-only, exactly as a textual summary already is.

## Relationship to Engineering Philosophy

This decision does not introduce a new principle — it applies an existing one to a presentation form GridDefence has not yet used.

- **PSS®E provides Operational Context; GridDefence manages engineering information** (§6, Layer 2). A network visualisation is one more way of presenting that same Operational Context — never a redefinition of what it is or who owns it.
- **Engineers make engineering decisions; GridDefence detects engineering impacts** (§2, §10 Principle 10). A visualisation may make an impact easier to *see*, but the detection, and the decision, remain exactly where they already are.
- **The application never replaces engineering judgement** (§10 Principle 1). A picture of the network is not a judgement about the network — an engineer still decides whether what they see is acceptable.

Visualisation, in short, assists engineers in *understanding* Operational Context. It does not become an engineering authority, and it does not change what already is one.

## Scope

This EDR is deliberately broad. It records an engineering philosophy, not a design.

It does **not** prescribe:
- implementation technology,
- graph or charting libraries,
- rendering engines,
- layout algorithms,
- UI design,
- interaction behaviour.

Those decisions belong to future UX and implementation phases, each of which should be evaluated against this EDR's own decision and rationale, not against a specific technology this document does not name.

## Future Opportunities

Examples of where this philosophy may later be applied — illustrative, not commitments, and not a roadmap:

- **PSS/E Import Preview** — a spatial view of the uploaded snapshot, alongside its existing Snapshot Summary/Registry Matching text (§8.9b).
- **Current Network Overview** — a view of the network GridDefence currently holds as Current, for general situational awareness.
- **Network Explorer** — the existing static Network Model's own future visual counterpart to its already-textual substation/bay/connectivity browsing.
- **Scheme Design** — a spatial view of which substations, bays, or boundary lines a candidate Stage's Shedding Actions actually touch.
- **Engineering Validation** — a spatial view of where a Continuous Validation finding's affected equipment sits in the network.
- **Network Heatmaps** — already named as a future Supporting Module ([07-future-roadmap.md](../07-future-roadmap.md) §3); this EDR's principle is the philosophy a heatmap implementation would need to satisfy.
- **Historical Network Comparison** — a spatial "what changed" view between two points in the network's history, complementing the already-envisioned textual comparison ([07-future-roadmap.md](../07-future-roadmap.md) §3).

## Non-Goals

Visualisation, under this decision, is explicitly **not** intended to:
- perform power system simulation,
- calculate engineering decisions,
- recommend defence schemes,
- replace engineering judgement,
- become a GIS platform,
- become a SCADA mimic.

GridDefence remains an engineering decision-support platform. Adding a visual presentation of Operational Context does not change that; it is one more way of supporting the same engineer, making the same decision, on the same data.

## Consequences

**Positive:**
- Future Preview, Import Result, Network Explorer, and Supporting Module work has a settled philosophical basis for *why* a visual view is worth building, decided once here rather than re-argued in every future UX proposal.
- The Non-Goals section gives every future visualisation effort a clear, reusable boundary check — the same "does it read or does it write" test [07-future-roadmap.md](../07-future-roadmap.md) §5 already applies to Supporting Modules generally.

**Negative / trade-offs:**
- This EDR authorizes no implementation by itself — a future phase must still design, scope, and build any specific visualisation, and must re-justify its own technology and interaction choices at that time.
- A visualisation that quietly begins computing something beyond what is already stored (a derived risk indicator, an inferred island) would violate this decision even if visually indistinguishable from one that does not — reviewers of future visualisation work should check this specifically, since the boundary is not visible in a screenshot.
