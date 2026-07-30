# GridDefence Visual Theme

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15 Frontend Standards, A12 Frontend Calculation Boundary). Sits between the [Design System Philosophy](design-system-philosophy.md) (the enduring rules) and the future Design System (the implementation vocabulary). Expresses the approved direction of the [Design Reference Library](../design/README.md); aligns with the [UI/UX Philosophy](ui-ux-philosophy.md); subordinate to the [Engineering Philosophy](../engineering/01-engineering-philosophy.md).

**This document names the GridDefence visual identity; it is not an implementation guide.** It answers *"what should GridDefence look and feel like?"* — never *"how should a button be built?"* It is deliberately technology-neutral: it defines no colour values, type scales, spacing scales, tokens, variables, components, or framework. Those belong to the future Design System.

---

## 1. Purpose

The GridDefence Theme is the platform's **named visual identity** — the single, concrete answer to what GridDefence looks and feels like, which every future workspace, page, and component should inherit.

It completes, without replacing, the layers around it:

- The **[Engineering Reference Library](../engineering/)** defines behaviour; the theme never alters it.
- The **Architecture Documentation** defines structure; the theme dresses that structure, never redraws it.
- The **[Design System Philosophy](design-system-philosophy.md)** defines the enduring *rules* a theme must satisfy (semantic colour, restraint, meaning-consistency, a calm non-decorative instrument) but deliberately commits to no palette, type, or spacing. **This document fills those deliberately-empty slots with GridDefence's actual, approved choices** — still as roles and character, never as values.
- The **[Design Reference Library](../design/README.md)** holds the approved mockups; this theme is the language those mockups express, stated once in prose so it can be applied where no mockup yet exists.

Where the philosophy says *"colour must be semantic and restrained,"* the theme says *"GridDefence's colour is a restrained cool-blue language on light surfaces."* Where the future Design System will say *"here is the exact value,"* the theme says *"here is what it must mean and feel like." *

## 2. Visual Identity

GridDefence should feel like a **professional engineering instrument** — communicating professionalism, engineering confidence, trust, operational awareness, clarity, precision, and calmness. It is the interface a power-system engineer should be comfortable working within for long, focused sessions, and should trust the way they trust a well-made instrument: quiet, precise, and honest.

The identity is **calm and analytical, not expressive.** It recedes so engineering information can be seen ([UI/UX Philosophy](ui-ux-philosophy.md) §3; [Design System Philosophy](design-system-philosophy.md) §2). Nothing in the theme should feel like an ERP, a consumer app, or a marketing site; everything should feel considered, stable, and built for engineering work.

## 3. Colour Philosophy

GridDefence uses a **restrained, semantic colour language**, described here by role, never by value:

- **Primary brand colour** — a **cool blue** that carries the brand and marks the single most important action in a view. It is the interface's strongest voice and is therefore used sparingly, so that voice keeps its meaning.
- **Supporting colours** — quieter blues and accents that relate to the primary, used for secondary emphasis and structure without competing with it.
- **Neutral surfaces** — **white working surfaces** set against **soft, atmospheric blue** framing; neutrality is the default, so that any colour reads as intentional.
- **Text hierarchy** — **deep-navy** primary text with progressively quieter tones for secondary and supporting text, giving a clear reading order without relying on colour alone.
- **Emphasis and status** — reserved, meaningful colours for engineering states (severity, category, condition), consistent everywhere they appear.
- **Interaction colours** — hover, focus, and selection states derived from the primary language, so interactivity is recognisable and consistent across every surface.

**Colour is restrained by design, not by austerity.** In a largely neutral interface, colour draws the eye precisely *because* it is scarce; an interface where everything is coloured has no way left to say "look here." And, decisively: **colour communicates engineering meaning and must never manufacture an engineering conclusion.** A status colour may *reflect* a state the data already holds; it must never assert one the system has decided, which would be the interface performing engineering judgement it must not perform ([EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md), [EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md)).

## 4. Light Theme Philosophy

GridDefence adopts a **light theme** as its approved direction because it best serves the platform's primary work: reading, comparing, and reasoning about dense engineering information over long periods.

- **Readability and engineering documentation** — schemes, registries, findings, and audit records are engineering documents; a light, high-contrast surface reads with the seriousness and legibility of one.
- **Long-duration use** — a calm, evenly-lit surface sustains long focused sessions in the well-lit office and control environments where this work happens.
- **Information density and contrast** — dark text on light surfaces holds up under the density GridDefence needs, keeping columns of numbers and dense tables clearly legible.
- **Reduced cognitive effort** — a quiet, familiar, document-like surface asks the least of the engineer's attention, leaving it for the engineering.

This is the approved direction, not a permanent exclusion of alternatives; a future accessibility or environmental need (§12, §13) could introduce a complementary treatment, which would refine this language rather than abandon it.

## 5. Surface Philosophy

GridDefence composes a small hierarchy of **surfaces**, distinguished by role, not by implementation:

- **Application shell** — the continuous, quiet frame that holds everything; the most recessive surface, present but never competing with content.
- **Workspace** — the primary working surface where engineering activity happens; the calm white ground on which information sits.
- **Cards and panels** — grouping surfaces *within* a workspace that gather related information, giving structure without fragmentation.
- **Dialogs** — focused surfaces for a single, deliberate interaction that momentarily takes precedence.
- **Overlays** — transient surfaces for brief, contextual information that appear and dismiss without disturbing the work beneath.

Their **relationship** is one of containment and focus: each inner surface is more specific and more momentary than the one that holds it, and all surfaces in a view reflect the *same* authoritative context — they never disagree about what they are showing ([Workspace Architecture](workspace-architecture.md) §4). Surfaces organise attention; they do not decorate it.

## 6. Typography Philosophy

Where the [Design System Philosophy](design-system-philosophy.md) §6 states what typography must *achieve*, the theme commits to its *character*: GridDefence's type is a **clean, contemporary, highly legible sans-serif** voice — unadorned, even in weight and colour, engineering rather than editorial in feel (no specific typeface is named here). Within that character:

- **Readability first** — legible at the sizes and densities engineering views actually use, and comfortable across long sessions.
- **Clear hierarchy** — consistent, unmistakable distinction between a heading, a value, a label, and supporting text, so a dense view parses without effort.
- **Engineering precision** — digits are unambiguous and columns of numbers align and compare cleanly; a misread number here is an engineering error, not a cosmetic one.
- **Calmness** — steady, unfussy type that conveys authority without drawing attention to itself.

## 7. Spatial Philosophy

Space in GridDefence is **structural, not luxurious**. Whitespace, rhythm, balance, alignment, and grouping exist to make engineering information easier to understand — never to make the interface look expensive or sparse.

- **Grouping** — related information reads as related through proximity; unrelated information is given separation. Space is the clearest grouping mechanism available.
- **Alignment and rhythm** — consistent alignment communicates relationship and keeps dense views scannable; a steady spatial rhythm lets the eye move predictably, which matters *more* as density rises.
- **Breathing room with purpose** — space is spent to create clarity and structure, not to signal minimalism. In an engineering instrument, whitespace is a tool for understanding.

## 8. Visual Density

GridDefence is an engineering platform, and engineering work benefits from seeing more at once. **Density is intentional here — a deliberate response to what the engineer needs to see, never clutter and never emptiness.**

Density is **not uniform.** Different workspaces legitimately need different densities: a registry that must be scanned and compared is dense by nature; a focused review of a single decision may be calmer. The theme expects this variation and asks only that density always be *structured* — legible through hierarchy, alignment, and restraint ([Design System Philosophy](design-system-philosophy.md) §3) — never merely packed.

Crucially, **the login page establishes the visual language, not the density budget.** Its generous, atmospheric spacing belongs to an entry moment (§10); authenticated engineering workspaces inherit its *language* while adopting the *structured density* their engineering work requires. No exact measurements are prescribed here; density is an engineering judgement per surface, made within the language.

## 9. Elevation Philosophy

Elevation in GridDefence is **minimal and meaningful.** Subtle depth exists to communicate three things, and little else:

- **Hierarchy** — which surface contains which, so structure is legible at a glance.
- **Focus** — what currently holds the engineer's attention (a dialog, an active panel).
- **Interaction** — what is interactive or in an interactive state.

Elevation **supports understanding, not decoration.** A soft, restrained sense of depth that says "this is above that" earns its place; layered, dramatic depth applied for visual richness does not. As with colour, restraint is what keeps elevation meaningful.

## 10. Environmental Illustration

Illustration, atmospheric backgrounds, and imagery have a **specific and bounded** place in GridDefence.

The **login page is an unauthenticated entry experience** — a first impression before any engineering work begins — and its full-bleed atmospheric imagery is appropriate *there*. But **authenticated engineering workspaces inherit the visual language, not necessarily the atmospheric illustration.** A working instrument is not a landing page; a photographic backdrop that is welcoming at the door becomes visual noise behind a substation registry or a topology view.

The rule, stated memorably: **carry the language inward, not the atmosphere.** Inherit the palette, the deep-navy type, the white surfaces, the strong-blue primary action, the subtle elevation, and the calm tone; leave the entry-moment imagery at the entry. Where imagery or illustration serves an *engineering* purpose inside the application (a network view, a diagram), it is content, governed by [EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md) — not decoration.

## 11. Brand Identity

The GridDefence logo — a shield enclosing a transmission-tower mark with the wordmark — is the platform's mark of identity ([Design Reference Library](../design/README.md) §8). Its role in the theme is to communicate **confidence and belonging without overwhelming engineering content.**

Branding should be present and consistent — enough that every surface clearly belongs to the same product — and quiet enough that it never competes with the engineering information the engineer came to see. In an instrument, the brand is a steady signature, not a headline. It remains stable across the application unless a deliberate, approved rebranding occurs.

## 12. Accessibility Philosophy

Accessibility in GridDefence is treated as **engineering integrity applied to perception** — a philosophy, not a checklist:

- **Readability** — information is legible to engineers of varying vision, at real working sizes, without strain.
- **Contrast** — text and meaningful elements stand clearly against their surfaces, sustaining the platform's high-readability commitment.
- **Colour independence** — meaning carried by colour is *always* also available without it, through label, shape, or position; colour is a channel, never the only channel. This is both an accessibility requirement and an honesty requirement — an engineer must never depend on a hue they may not perceive to read an engineering state ([Design System Philosophy](design-system-philosophy.md) §6).
- **Clarity and reduced fatigue** — a calm, low-noise, predictable interface is an accessible one; it lowers the perceptual and cognitive cost of long engineering sessions for everyone.

Accessibility is not a mode bolted on later; it is part of what "clear, trustworthy engineering instrument" means.

## 13. Theme Evolution

The GridDefence Theme is expected to **mature over years, refining its language rather than replacing it.** Future designs should deepen and clarify this identity — better hierarchy, better density, better accessibility — while keeping GridDefence recognisably itself.

Evolution is **evolutionary, not revolutionary** ([Design Reference Library](../design/README.md) §5): the visual identity should feel continuous across its whole life, never rebuilt from scratch on a trend. A genuine improvement is welcome, with justification against Engineering, Architecture, and visual continuity — and when adopted, it is raised into the shared language and propagated, not left as a fragment. A change to a *principle* rather than an expression belongs in the [Design System Philosophy](design-system-philosophy.md) or an ADR.

## 14. Relationship with the Future Design System

This document and the future Design System are two halves of one intent, and must not be confused:

- **The GridDefence Theme (this document) explains *what GridDefence should feel like*** — the identity, in roles and character, technology-neutral.
- **The future Design System will explain *how to build that experience consistently*** — the concrete vocabulary of values, scales, states, and reusable parts that realise this identity in a specific technology.

The **Design System will inherit this document, not replace it.** When the two are read together, this theme is the durable intent that outlives any particular Design System, and the Design System is the current, replaceable machinery that makes the intent real. If a future Design System is ever rebuilt on new technology, this theme should still be true; that is the test of whether this document stayed at the right altitude.

## 15. Final Principle

GridDefence should look the way trustworthy engineering feels: **quiet, precise, and honest** — a calm instrument that makes engineering information clear and asks the engineer's attention only for the engineering.

The theme's whole purpose is to disappear into that clarity. Its success is not that an engineer admires the interface, but that they forget it is there — because nothing in it stood between them and the truth they came to understand.
