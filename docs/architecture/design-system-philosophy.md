# GridDefence Design System Philosophy

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15 Frontend Standards, A12 Frontend Calculation Boundary). Inherits from the [UI/UX Philosophy](ui-ux-philosophy.md); subordinate to the [Engineering Philosophy](../engineering/01-engineering-philosophy.md), which both serve and neither redefines.

Related: [EDR-006 — Operational Context should be visualized, not only summarized](../engineering/edr/EDR-006-operational-context-visualization.md); [EDR-004 — decision support, not automation](../engineering/edr/EDR-004-decision-support-not-automation.md).

**This is a visual philosophy, not a design system.** The [UI/UX Philosophy](ui-ux-philosophy.md) says how engineers should *experience* GridDefence. This document says how that experience should be *visually expressed* — the design direction a future Design System, Component Library, and Frontend will inherit. It defines no colours, type, spacing, icons, components, or technology; those are downstream decisions (§10), made against this direction, never fixed here.

---

## 1. The Bridge

The UI/UX Philosophy established one progression: engineering data becomes **awareness**, **understanding**, and **confidence**, and stops — deliberately — at the engineer's decision.

Visual design is how that progression is made visible. Every visual choice in GridDefence is answerable to one question: *does this help the engineer become more aware, understand more clearly, and decide with more confidence?* A choice that only decorates has, at best, spent attention it did not earn; at worst, it has spent attention that awareness needed. Visual design here is an engineering instrument, not a finish applied over one.

## 2. Visual Identity

GridDefence should feel closer to a professional engineering instrument than to business software. Its character is **calm, precise, analytical, and trustworthy** — an interface that recedes so the engineering data can be seen, rather than one that competes with it for attention.

Two of the commonly-cited adjectives deserve a caution rather than agreement:

- **"Modern"** is a moving target and a poor north star — today's modern is next decade's dated. GridDefence should aim for *timeless clarity* instead; an interface built for legibility ages far more slowly than one built for a current style.
- **"Data-dense"** is a means, not an identity (§3). Density is valuable only when it raises awareness; density pursued for its own sake becomes clutter (§3).

Decoration is not neutral. In an engineering instrument, ornament that carries no engineering meaning is a small, permanent tax on every engineer who must look past it. The visual language should be quiet by default, and reserve emphasis for the moments engineering meaning genuinely warrants it.

## 3. Information Density

Engineering work benefits from seeing more at once. An engineer comparing loads across a region, or scanning a scheme's assignments, is served by an overview that fits — not by a sparse layout that hides the whole behind repeated scrolling.

But **density is not the same as clutter.** Clutter is *undifferentiated* density — everything presented with equal weight, so nothing stands out. Good density is *structured* density — a great deal of information, organised so the eye can find what it needs. The design language should make dense views legible through hierarchy, alignment, and restraint, not make them tolerable by removing information the engineer needs.

Two disciplines follow:

- **Progressive disclosure.** Present the awareness-level view first; let detail, history, and audit be reached on demand rather than shown all at once. The overview and the detail are both first-class — the design should move between them fluidly, never force a choice between an uninformative summary and an overwhelming dump.
- **Readability under density.** The denser a view, the more it depends on consistent alignment, clear grouping, and typographic clarity (§6, §7) to stay readable. Density earns its place only when the design keeps it legible.

## 4. Visual Hierarchy

Information should flow the way engineering attention flows:

```text
Summary → Awareness → Context → Detail → History → Audit
```

Hierarchy is how a view expresses the engineering progression (§1) visually — what an engineer sees first, what is one step away, what is available when specifically sought. The most consequential engineering information should be the most visually available; supporting evidence should be present but subordinate; provenance and audit should be reachable but never in the way of the decision they support.

This flow is a **default emphasis, not a fixed sequence.** Engineering work is non-linear ([UI/UX Philosophy](ui-ux-philosophy.md) §5) — an engineer may enter at a finding, a history entry, or an audit record and work outward. Hierarchy should therefore be understood as *depth available on demand* from wherever the engineer is looking, not as a single mandatory top-to-bottom path.

## 5. Presentation Surfaces

Dashboards, tables, maps, topology diagrams, charts, timelines, and comparison views are **complementary expressions of one body of engineering knowledge — not competing UI elements.** Each is strongest at a particular kind of awareness (§3 of the [UI/UX Philosophy](ui-ux-philosophy.md)): a map for spatial, a topology diagram for network, a table for precise comparison, a timeline for historical, a comparison view for "what changed."

The design language's responsibility is that these surfaces read as **one system**, not a collection of separately-styled tools. The same value should look like the same thing wherever it appears; a state shown one way in a table should be recognisable when the same state appears on a map. Coherence across surfaces is what lets an engineer follow a relationship from one to another ([UI/UX Philosophy](ui-ux-philosophy.md) §4) without re-learning the visual language at each step. The surfaces differ in *form*; they must not differ in *meaning*.

## 6. Colour Philosophy

Colour in GridDefence is **semantic before it is aesthetic.** A colour should mean something engineering — a state, a severity, a category — and mean the same thing everywhere. Colour chosen purely for appearance, with no consistent engineering meaning, trains the engineer to ignore it, which then weakens the colours that do carry meaning.

Principles, stated without any specific palette:

- **Restraint gives colour its signal.** In a calm, largely neutral interface, colour draws the eye precisely because it is used sparingly. An interface where everything is coloured has no way left to say "look here."
- **Colour must never assert a conclusion the data does not hold.** This is where colour meets engineering integrity: a "problem" colour applied to something the system has *decided* is a problem would be the interface computing an engineering judgement, which it must not do ([EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md), [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md)). Colour may reflect a state the data already carries; it may never manufacture one.
- **Colour is a channel, never the only channel.** Meaning conveyed by colour must also be available without it — through label, shape, or position — for accessibility and for the many conditions (colour vision deficiency, print, poor displays, glare in an operations room) under which colour alone fails.
- **Consistency over cleverness.** A small, disciplined set of meanings applied consistently serves engineering far better than a rich palette applied expressively.

This document deliberately defines no colours. It defines the rules any future palette must satisfy.

## 7. Typography Philosophy

Typography is the primary carrier of engineering information, and in a data-dense instrument its clarity is not cosmetic — it is functional.

- **Readability first**, at the sizes and densities engineering views actually use, sustained over long working sessions.
- **Hierarchy through type** — clear, consistent distinctions between a heading, a value, a label, and supporting text let an engineer parse a dense view without effort.
- **Numerical clarity is a first-class engineering concern.** GridDefence is full of numbers that must be read exactly and compared down a column — MW figures, thresholds, voltages, counts. The type treatment must make digits unambiguous and columns of numbers align and compare cleanly. Misreading a number here is an engineering error, not a cosmetic one.
- **Documentation-grade legibility** — schemes, findings, and audit records are engineering documents, and should read with the seriousness and clarity of one.

This document recommends no typeface. It defines what the typography must achieve.

## 8. Spatial Philosophy

Space is structural, not empty. How elements are grouped, aligned, and spaced *is* information — it tells the engineer what belongs together and what is distinct, before a single word is read.

- **Grouping** — related information reads as related through proximity; unrelated information is given separation. Space is the cheapest and clearest grouping mechanism available.
- **Alignment** — consistent alignment communicates relationship and makes dense views scannable; misalignment introduces visual noise the eye must work to discount.
- **Rhythm** — a consistent spatial rhythm lets an engineer's eye move predictably through a view, which matters more, not less, as density rises.
- **Whitespace with purpose** — space should be spent to create structure and legibility, not to look sparse. In an engineering instrument, whitespace is a tool for clarity, not a stylistic goal in itself.

## 9. Visual Consistency

Consistency is what lets the platform feel like **one system** rather than many. When the same thing always looks the same, the engineer learns the visual language once and then spends attention on engineering, not on re-interpreting the interface. Consistency is also a quiet form of trust: an instrument that behaves predictably is one an engineer can rely on.

But consistency must never harden into a cage. The distinction that keeps it healthy:

- **Consistency of *meaning* must hold.** A state, a severity, a value must mean the same thing everywhere. This is non-negotiable — it is what §5 and §6 depend on.
- **Consistency of *form* may evolve.** How that meaning is best expressed can improve over the platform's life; a new surface or a new module may find a clearer expression than the current one. When it does, the improvement should be adopted *and propagated* — raising the shared language — rather than either suppressed for uniformity or left as a local exception that fragments it.

Consistency is the default that innovation must earn its way past — not a rule that forbids it.

## 10. The Implementation Boundary

Four architectural layers, each depending on the one above and replaceable without invalidating it:

```text
Design Philosophy      — this document: what the interface should mean and feel like, and why
        ↓
Design System          — the shared vocabulary: semantic tokens, scales, states, and rules
        ↓
Component Library       — concrete, reusable implementations of that vocabulary
        ↓
Frontend Implementation — the actual product screens engineers use
```

They are separate on purpose:

- **The philosophy outlives its implementations.** Component libraries and frameworks will be rewritten over a platform expected to run for many years; the reasons behind the visual language should not have to be rediscovered each time. This document must remain valid when today's technology choices are gone.
- **Each layer answers a different question** — *why* (philosophy), *what vocabulary* (system), *what concrete parts* (library), *what product* (implementation). Collapsing them couples a durable engineering intent to a disposable technical decision.
- **Change flows downward, never upward.** A framework change may not quietly redefine what a colour or a state *means*; meaning is set here and in the Design System, and implementation inherits it. This mirrors the platform's own rule that presentation never becomes an authority of its own ([UI/UX Philosophy](ui-ux-philosophy.md) §6).

## Extensibility

The visual language must accommodate dashboards, maps, analytics, registries, schemes, and modules not yet imagined — without redesign. The enabling philosophy is **semantic over specific**: define durable *meanings* (a state, a severity, a category, a level of emphasis) rather than a fixed catalogue of screens. A future module then inherits the meanings and composes new expressions from them, extending the language instead of breaking it.

A design language built from fixed layouts must be redesigned for every new kind of view. One built from consistent meaning grows to fit views its authors never anticipated — which, for a platform expected to expand for years, is the only property that ultimately matters.

## Final Principle

The GridDefence design language exists to make engineering knowledge clear, trustworthy, and immediately legible — and to do so quietly, so that what the engineer notices is the engineering, not the interface.

Every visual decision serves awareness, understanding, and confidence.

None of them makes the decision.
