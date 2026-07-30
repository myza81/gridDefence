# GridDefence UI/UX Philosophy

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15 Frontend Standards, A12 Frontend Calculation Boundary). Subordinate to the [Engineering Philosophy](../engineering/01-engineering-philosophy.md), which it serves and never redefines.

Related: [EDR-006 — Operational Context should be visualized, not only summarized](../engineering/edr/EDR-006-operational-context-visualization.md); [EDR-004 — decision support, not automation](../engineering/edr/EDR-004-decision-support-not-automation.md); [ADR-010 — Engineering Decision-Support Philosophy](../adr/ADR-010-engineering-decision-support-philosophy.md); [engineering-workspace-architecture.md](engineering-workspace-architecture.md).

**This is a design philosophy, not a UI specification.** It states what the interface is *for* and the boundaries it must never cross. It deliberately does not prescribe screens, components, layouts, libraries, or visual treatments — those are implementation choices, re-decided each phase against this philosophy, never fixed here.

---

## 1. Vision

The GridDefence interface exists to serve the engineering philosophy, not to redefine it.

That philosophy is already settled: **GridDefence detects engineering impacts; engineers make engineering decisions** ([01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §2, §10). The application never replaces engineering judgement.

The interface's purpose follows directly from this. It does not exist to display screens, manage tasks, or move an engineer through a process. It exists to progressively transform engineering data into engineering **awareness**, engineering **understanding**, and engineering **confidence** — while preserving the engineer as the final decision maker.

Everything that follows is one elaboration of that single sentence.

## 2. The Engineering Progression

Every part of the interface serves one progression:

```text
Engineering Data
  ↓
Engineering Information
  ↓
Engineering Awareness
  ↓
Engineering Understanding
  ↓
Engineering Confidence
  ↓
Engineering Decision
```

- **Data** is what the system stores.
- **Information** is data made legible — named, located, related.
- **Awareness** is the engineer sensing the state of the system.
- **Understanding** is the engineer grasping *why* the system is in that state.
- **Confidence** is the engineer's justified assurance in the decision they are about to make.
- **Decision** is, and always remains, the engineer's.

The interface's job is to move the engineer along this progression. It never reaches the final step for them ([EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md), [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md)).

A screen that shows data but leaves the engineer no more aware has done its mechanical job and failed its engineering one.

## 3. Engineering Awareness

**Visualisation is a mechanism. Engineering awareness is the objective** ([EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md)).

The platform does not exist to draw tables, maps, and charts. It exists to make the engineer more aware of the transmission system they are responsible for. A presentation earns its place only by increasing one of these:

- **spatial** awareness — where things are
- **network** awareness — how they connect
- **operational** awareness — what state they are in now
- **load** awareness — what they carry
- **historical** awareness — how they changed
- **scheme** awareness — what defends them
- **impact** awareness — what a change affects
- **validation** awareness — what no longer holds

The form — table, map, topology, dashboard — is chosen to serve the awareness the engineer needs, never for its own sake. When a number conveys awareness better than a picture, the number is correct; when a picture does, the picture is. The form is negotiable. The awareness is not.

## 4. Connected Engineering Knowledge

GridDefence is one engineering knowledge ecosystem, not a set of independent modules that happen to share a menu.

Every engineering object is connected to the others:

```text
Substation → Equipment → Relay → Topology → Operational Loading
   → Scheme Assignment → Validation → Reports → History → Audit
   → Map → Analytics → future modules
```

These are not separate destinations. They are views onto one connected body of engineering knowledge. The interface should let an engineer move along these relationships naturally — from a substation to its equipment, from a piece of equipment to the scheme that assigns it, from that scheme to the validation finding that questions it, from that finding to the history that explains it — without feeling they have left one application and entered another.

The measure of success is simple: the platform feels like a single connected system, and no relationship an engineer needs to follow is a dead end.

## 5. Engineering Exploration and Discovery

Most enterprise software optimises only for task completion. GridDefence must also support engineering **investigation**.

Engineers do not only complete forms. They ask questions:

- What is connected to this?
- What changed, and when?
- What else is affected?
- Why is this so?

The interface must make these questions easy to ask and to follow, across related engineering information, in any order. Engineering work is frequently non-linear ([engineering-workspace-architecture.md](engineering-workspace-architecture.md)) — the interface must never assume every path is a straight line from a fixed start to a fixed finish.

In supporting investigation, the platform also makes engineering **discovery** easier — surfacing relationships an engineer might otherwise not have seen: hidden topology relationships, boundary load pockets, engineering impacts, historical changes, correlation problems, unexpected loading behaviour, validation findings.

But the platform only makes discovery easier. It never makes the discovery *for* the engineer, and it never replaces the engineering judgement that decides what a discovery means. It lowers the effort of looking; the seeing, and the deciding, remain the engineer's.

## 6. Design Principles

These principles hold regardless of technology, screen, or era.

1. **Awareness over display.** A view justifies itself by the awareness it creates, not by the data it renders.
2. **Presentation, never computation.** The interface presents engineering facts and backend-computed results; it never derives an authoritative engineering conclusion of its own (CLAUDE.md A12, [EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md)).
3. **Honest reporting.** The interface shows what the system found, exactly as found — never a state it has quietly "helpfully" adjusted ([EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md)).
4. **Connection over containment.** Prefer letting the engineer follow a relationship over trapping them inside one module's boundary.
5. **Investigation over linearity.** Support questions asked in any order; do not impose a single path where engineering work has none.
6. **The engineer decides.** Every path ends at an engineer's decision, never at the system's.

### Future capability

New capabilities will arrive over the platform's life — richer visualisation, faster correlation, more anticipatory ways of surfacing relevant engineering information. Whatever their underlying technology, they enter under one unchanging test:

> Does this move the engineer further along the engineering progression — toward awareness, understanding, and confidence — while leaving the decision itself with the engineer?

A capability that advances the engineer's awareness is welcome, whatever it is built from. A capability that makes the engineering decision, however capable, is not GridDefence. This test is deliberately technology-neutral: it was true before today's tools and will remain true after them.

## 7. What the Interface Must Never Do

- Make an engineering decision, flag pass/fail, or approve/activate on the engineer's behalf.
- Compute an authoritative engineering result client-side (CLAUDE.md A12).
- Alter, resolve, or hide an engineering finding to present a tidier picture.
- Duplicate, or become a second source of, engineering truth ([EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md)).
- Force a linear workflow onto non-linear engineering investigation.
- Mandate a specific technology, component, layout, or visual treatment — those are implementation choices, re-decided per phase against this philosophy, never fixed here.

## Final Principle

GridDefence progressively transforms engineering data into engineering awareness, engineering understanding, and engineering confidence — and then stops, deliberately, at the engineer's decision.

The interface's highest purpose is a confident, well-informed engineer.

It is never a substitute for one.
