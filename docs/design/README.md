# GridDefence Design Reference Library

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1. Subordinate to the [Engineering Reference Library](../engineering/) and the [Architecture Documentation](../architecture/). Read together with the design-architecture lineage — [UI/UX Philosophy](../architecture/ui-ux-philosophy.md), [Design System Philosophy](../architecture/design-system-philosophy.md), [Application Shell Architecture](../architecture/application-shell-architecture.md), [Navigation Architecture](../architecture/navigation-architecture.md), [Workspace Architecture](../architecture/workspace-architecture.md).

**This is the governing document for the Design Reference Library — the design equivalent of the Engineering Philosophy, not a design specification or implementation guide.** It explains why this library exists, how it relates to Engineering and Architecture, how approved references should be used and interpreted, and how the visual language should evolve. It defines no components, values, or technology, and it names no framework.

---

## 1. Purpose

The Design Reference Library captures the **approved visual direction** of GridDefence — its brand identity, colour language, layout and spacing philosophy, visual hierarchy, information density, atmosphere, and interaction character — through a growing set of approved, concrete artefacts (mockups and brand assets).

It **complements** the Engineering Reference Library and the Architecture Documentation; it replaces neither. Engineering defines *what* the platform does; Architecture defines *how* it is organised; this library defines *how it looks and feels*. Its purpose is to preserve visual consistency **while the application keeps evolving** — not to freeze the interface. Every approved mockup adds to the shared visual knowledge of the project, so that across a platform expected to grow for years, **every GridDefence surface feels like the same product**, built for the same professional power-system engineers.

**Position in the authoritative hierarchy:**

```text
Engineering   (docs/engineering/)   — behaviour     (WHAT)
      ↓
Architecture  (docs/architecture/)  — structure     (HOW)
      ↓
Design        (docs/design/)        — experience    (LOOK & FEEL)
      ↓
Implementation                      — supports all three
```

Design must always support Architecture; Architecture must always support Engineering. When layers appear to conflict, the higher layer prevails and the design adapts.

## 2. Relationship with Engineering

**Engineering behaviour is always authoritative.** The design exists to communicate engineering information clearly — to help an engineer move from data to a confident decision (Engineering Data → Information → Awareness → Understanding → Confidence → Decision).

Design must **never introduce anything that changes engineering meaning.** A visual treatment may make an impact easier to *see*, but it must not detect the impact, decide the outcome, or imply a conclusion the [Engineering Reference Library](../engineering/) does not define ([EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md), [EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md)). Colour, emphasis, and arrangement present engineering facts; they never manufacture them. Where a mockup appears to imply a behaviour, Engineering — not the mockup — governs whether that behaviour is real.

## 3. Relationship with Architecture

Architecture defines the platform's **organisation, boundaries, and responsibilities** — the shell that provides continuity, the navigation that reaches and orients, the workspaces where engineering work happens, and the domain modules that own truth. **This library expresses those architectural concepts visually, and follows them.**

A visual reference can never redraw an architectural boundary or reassign ownership: it shows what the shell, a workspace, or a domain *looks like*, never changes what each *is*. This library provides the concrete visual direction that the [Design System Philosophy](../architecture/design-system-philosophy.md) describes in principle — the philosophy is the enduring *why*, this library is the approved *what it looks like* — and both remain bound by the philosophy's rules (semantic colour, restraint, meaning-consistency, a calm non-decorative instrument).

## 4. Purpose of Design References

The files in this directory are **approved visual references**. Today they include `logo.png` and `login_page.png`; the library is expected to grow to include references such as the **application shell, dashboard, navigation, registry workspace, topology workspace, map workspace, and comparison workspace**, among others.

These are **design references, not pixel-perfect specifications, and must never be copied literally.** Each reference communicates the platform's **visual language, spacing, hierarchy, composition, atmosphere, and interaction philosophy** — not the exact position of any element on a particular screen. Two consequences follow:

- **Extract the language, not the layout.** Take the palette relationships, type hierarchy, elevation, spacing rhythm, density, and tone — not one screen's precise measurements.
- **A reference is evidence of the language, not the boundary of it.** A pattern's absence from the current references does not forbid it; a new engineering surface may need expressions no existing mockup shows, and inventing them *within* the language is expected.

## 5. Design Evolution

**Approved references establish direction; they do not freeze the design.** GridDefence is expected to improve for years, and its visual language should improve with it. Evolution here should be **evolutionary, not revolutionary** — each approved design improves the application while remaining recognisably part of the same product.

- **Do not preserve a poor visual decision merely because it already exists.** Longevity is not authority.
- **A better solution is welcome — with justification.** When proposing an evolution, state *why it is better* (for engineering understanding, clarity, accessibility, or scalability), *how it aligns* with Engineering and Architecture, and *how it stays recognisably the same product*. All three are required.
- **Distinguish objective concerns from preferences.** Accessibility, readability, consistency, and scalability are *objective* reasons to evolve; taste is a *subjective* one. Both are legitimate inputs, but they carry different weight and should be labelled as what they are.
- **When the language genuinely improves, raise the improvement into the shared language and propagate it** — never leave it as a local exception that fragments the product ([Design System Philosophy](../architecture/design-system-philosophy.md) §9). A change to a *principle* (not merely an expression) belongs in the Design System Philosophy or an ADR, not in this library alone.

## 6. Design Philosophy

GridDefence is an engineering platform. Its interface should communicate **professionalism, engineering confidence, trust, clarity, precision, calmness, and operational awareness** — the quiet authority of a professional engineering instrument.

It should **avoid** decorative interfaces, unnecessary animation, trendy consumer styling, dashboard clutter, excessive colour, and visual noise. Ornament that carries no engineering meaning is a permanent tax on every engineer who must look past it. GridDefence is not — and must not resemble — an ERP, CRM, accounting system, marketing site, admin template, or consumer productivity app.

**Timeless engineering software is preferred over fashionable design trends.** "Modern" is a moving target; clarity is not. An interface built for legibility and calm ages far more slowly than one built for a current style.

## 7. Current Approved Design Direction

The current approved direction is established by `login_page.png`. Described qualitatively — so the description guides without freezing implementation:

- **Light theme**, with a **cool-blue primary palette** and **white working surfaces**.
- **Soft, atmospheric blue backgrounds**; **deep-navy typography**; **strong blue primary actions**, used sparingly so the primary action carries clear signal.
- **Clean, purposeful whitespace**, **high readability**, **subtle elevation**, and **minimal visual noise** — a **calm engineering atmosphere**.

**Future interfaces should inherit this visual language** — but *interpreting a reference requires reading its context, not just its pixels.* The login page is an **unauthenticated entry point**: its full-bleed atmosphere and generous whitespace are appropriate *there*, before any engineering work begins. **Authenticated engineering workspaces are instruments, not entrances** — per the [Design System Philosophy](../architecture/design-system-philosophy.md) §2–§3 they should be calmer and denser, favouring *structured information density* over a marketing canvas. The rule that follows: **carry the language inward, not the atmosphere** — inherit the palette, deep-navy type, white surfaces, strong-blue primary action, subtle elevation, purposeful spacing, and calm tone; do not carry a full-bleed hero or low density into a substation registry or a topology workspace. For any reference, ask *which qualities are intrinsic to the language, and which are specific to that screen's engineering context?* Carry the former everywhere; leave the latter where it belongs.

## 8. Role of the Logo

`logo.png` is the **official brand reference** — a shield enclosing a transmission-tower mark, with the "GridDefence" wordmark. It establishes the platform's **brand identity, proportions, colours, and visual recognition**, and communicates the product plainly: protection of the grid, without decoration.

The logo should **remain consistent throughout the application unless a deliberate, approved rebranding occurs.** It is not a surface for per-screen reinterpretation; its stability is part of what makes the platform feel like one product. A rebrand is a deliberate act recorded as such — never an incidental drift.

## 9. Future Growth

This library is expected to **grow continuously.** Over time it should accumulate references documenting **new workspace concepts, new interaction patterns, new visualisations, new layouts, and improvements to existing designs.**

In doing so, the library becomes more than a style guide: it becomes the **historical visual evolution of GridDefence** — a record of how the product's engineering interface matured, and why. Each entry should be named by its **engineering purpose** (what engineering work it depicts), and each should make its **status and provenance clear**, so contributors can tell approved direction from exploration and never build against a draft as though it were settled.

## 10. Design Review Principles

When a new mockup is proposed, contributors should evaluate it against these questions:

- Does it **improve engineering understanding**?
- Does it **remain visually consistent** with the approved language?
- Does it **support the Engineering Philosophy**?
- Does it **support the Architecture Documentation**?
- Does it **reduce cognitive load**?
- Does it **improve engineering awareness**?
- Would **experienced power-system engineers be comfortable working with it for long periods**?

A concise set of decision tests behind those questions:

1. **Support test.** Does the choice *support* an engineering behaviour and an architectural structure? If it contradicts either, the higher layer wins and the design adapts (§1–§3).
2. **Judgement test.** Does it *present* engineering information, or *decide* an engineering conclusion? Presentation is design's; judgement is the engineer's (§2).
3. **Language test.** Is it an expression *within* the approved language, or a *change to* it? An expression is free; a change requires the §5 justification.
4. **Context test.** Is a quality intrinsic to the language, or specific to one screen's context? Carry the intrinsic; leave the contextual (§7).
5. **Literal-copy test.** Am I extracting the language, or reproducing a mockup pixel-for-pixel? The library forbids the latter (§4).

Summary rule, in the spirit of the architecture documents:

> A design reference establishes visual direction. It never overrides engineering behaviour, never redraws an architectural boundary, never decides an engineering conclusion, and is never reproduced literally — it is a sample of the language, evolved with justification, in service of the engineer.

## 11. Final Principle

The Design Reference Library exists so that GridDefence looks and feels like one calm, trustworthy engineering platform — recognisably itself on every surface, evolving for years without ever losing its identity or its integrity.

It gives the language and remembers its history; it never freezes the design, never overrides engineering, and never decides for the engineer.

Every visual decision earns its place the same way: by making a power-system engineer's path from engineering data to an engineering decision clearer, calmer, and more certain — and by never, in doing so, compromising the engineering truth beneath it.
