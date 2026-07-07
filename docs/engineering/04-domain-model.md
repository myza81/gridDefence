# GridDefence Engineering Domain Model

This document describes how GridDefence's engineering concepts relate to one another — as an engineer would describe them on a whiteboard, not as database tables, foreign keys, or API contracts. For the concepts themselves, see [02-engineering-concepts.md](02-engineering-concepts.md). For the corresponding software module boundaries, see `docs/architecture/domain-model.md` — that document describes *who owns what in the software*; this document describes *how the engineering ideas relate to each other*, independent of any implementation.

---

## 1. The Central Relationship Chain

```
Grid Defence Scheme
        │
        │ contains
        ▼
     Stage
        │
        │ contains
        ▼
 Shedding Action
        │
        │ references
        ▼
       Bay  ───────────── belongs to ─────────────▶  Substation
        │
        │ hosts
        ▼
Primary Equipment  (a Transformer or a Transmission Line)
        │
        │ operated by
        ▼
    Breaker
        │
        │ controlled by
        ▼
   Relay / IED   (future Relay Registry)
```

Read top to bottom: a **Scheme** is made of **Stages**; a **Stage** is made of **Shedding Actions**; a **Shedding Action** references a **Bay**; a Bay belongs to a **Substation** and hosts one piece of **Primary Equipment**; that equipment is operated by a **Breaker**, controlled by a **Relay/IED** — the future Relay Registry's own subject matter.

Two relationships from the previous version of this chain still hold, attached at the level where they actually apply: **Grid Defence Capability** (Relay Registry) validates the **Bay**, not the Primary Equipment it happens to host today — this is exactly why replacing a Bay's equipment does not require re-verifying capability. Primary Equipment's expected load contribution is evaluated against a **PSS/E Load Snapshot**, itself always captured within one **PSS/E Network Topology**, unchanged from before.

**Implementation correspondence** (see [08-engineering-terminology.md](08-engineering-terminology.md) for the complete table): the current implementation already represents a **Line Bay** as `CircuitTerminal` and a **Transformer Bay** as `TransformerTerminal` (both Equipment Registry) — the same Bay concept described above, under different, already-existing names. No implementation change is required by this clarification; see [EDR-005](edr/EDR-005-bay-as-engineering-identity.md).

Every arrow in this diagram is a real engineering relationship an engineer reasons about while designing a scheme (03-system-workflow.md) — none of it is an artifact of how the software happens to store the data.

---

## 2. Boundary Line Shedding — The Alternate Path

Not every Shedding Action targets one piece of equipment directly. A Boundary Line action targets a *set of network boundaries* instead:

```
 Shedding Action (Boundary Line type)
        │
        │ opens
        ▼
 Boundary Line  (one or more)
        │
        │ isolates
        ▼
  Load Pocket ── evaluated against ──▶ PSS/E Network Topology
        │
        │ contains
        ▼
   Substation (0..N, determined by topology, not hand-enumerated)
```

The key engineering distinction from the central chain above: a direct Shedding Action (Transformer Bay or Line Bay) references *one known Bay*, hosting one known piece of Primary Equipment, with a *known* load contribution. A Boundary Line action instead references a small number of lines whose *combined effect* — the Load Pocket they isolate — is derived from the network's actual topology, not enumerated by hand. This is why Boundary Line shedding depends so heavily on PSS/E Network Topology being accurate and current (02-engineering-concepts.md, **Boundary Line**).

---

## 3. Where Engineering Knowledge, Operational Context, and Engineering Decisions Meet

```
┌─────────────────────────────┐     ┌──────────────────────────────┐
│      Engineering Knowledge   │     │      Operational Context      │
│         (Layer 1)            │     │           (Layer 2)           │
│                               │     │                                │
│  Substation Registry          │     │  PSS/E Network Topology       │
│  Equipment Registry           │     │  PSS/E Load Snapshot          │
│  Line Connectivity Registry   │     │                                │
│  Relay Registry               │     │                                │
│  Sensitive Customer Registry  │     │                                │
└──────────────┬────────────────┘     └───────────────┬────────────────┘
               │                                       │
               │        both inform, neither owns      │
               └──────────────────┬────────────────────┘
                                  ▼
                    ┌───────────────────────────┐
                    │   Engineering Decisions    │
                    │        (Layer 3)           │
                    │                             │
                    │   Grid Defence Scheme       │
                    │   (Stages, Shedding         │
                    │    Actions, Metadata)       │
                    └─────────────────────────────┘
```

A Shedding Action's engineering validity depends on **both** layers below it — Engineering Knowledge answers "does this equipment exist, and can it be operated" (Substation, Equipment, Grid Defence Capability, Sensitive Customer exclusion), while Operational Context answers "what would happen if it were operated, right now" (expected load, topology-derived pocket boundaries). Neither layer ever writes into Layer 3 directly — an engineer's decision is what turns information from either layer into part of a scheme (see **Engineering Decision** in [02-engineering-concepts.md](02-engineering-concepts.md)).

---

## 4. The Scheme's Own Internal Lifecycle Relationship

```
Working Draft ──(Scheme Review)──▶ Published Scheme ──(superseded by next Published version)──▶ Archived Scheme
      ▲                                     │
      │                                     │
      └─────── new Working Draft opened ────┘
             (an engineer's own decision,
              possibly informed by a
              Continuous Validation finding)
```

A **Grid Defence Scheme** does not relate to its own past versions the way a Stage relates to its Shedding Actions (composition) — it relates to them *sequentially*, one state at a time, per **Scheme Lifecycle**. At any moment, exactly one version of a given scheme type is the Published Scheme; every other version is either a Working Draft (not yet reviewed) or an Archived Scheme (previously Published, now superseded).

---

## 5. Full Relationship Summary

| Relationship | Meaning |
|---|---|
| Scheme **contains** Stages | A scheme is composed of one or more ordered stages. |
| Stage **contains** Shedding Actions | A stage groups the specific actions triggered together. |
| Shedding Action **references** Bay | A direct (Transformer Bay / Line Bay) action targets one Bay — a permanent engineering identity, not whichever Primary Equipment it currently hosts. |
| Shedding Action **opens** Boundary Line(s) | A Boundary Line action instead targets one or more network boundaries. |
| Boundary Line(s) **isolate** a Load Pocket | The combined effect of opened boundary lines, derived from topology. |
| Bay **belongs to** Substation | Every Bay has exactly one home substation. |
| Bay **hosts** Primary Equipment | A transformer or transmission line, which may be replaced without changing the Bay's own identity. |
| Primary Equipment **operated by** Breaker, **controlled by** Relay/IED | The physical switching chain a Grid Defence action ultimately triggers (future Relay Registry). |
| Bay **validated by** Grid Defence Capability | Recorded in the Relay Registry; answers "can this Bay be shed." |
| Primary Equipment / Load Pocket **evaluated against** PSS/E Load Snapshot | Determines expected MW/MVAr contribution at a point in time. |
| PSS/E Load Snapshot **captured within** PSS/E Network Topology | A snapshot is only meaningful relative to the topology it was taken against. |
| Scheme **excludes** Sensitive Customer loads | A hard policy constraint checked before a load is ever offered as a candidate. |
| Scheme **progresses through** Scheme Lifecycle | Working Draft → Scheme Review → Published Scheme → Archived Scheme. |
| Scheme **carries** Engineering Metadata | Version, review, approval, remarks, and revision history, recorded permanently. |

This table, together with the diagrams above, is the complete engineering relationship model GridDefence is built around. Any future concept introduced into the system should be checked against this model first — if it does not fit one of these relationships, or a clear, justified extension of one, its place in the domain needs its own engineering discussion before it is added (see [05-design-principles.md](05-design-principles.md), "Architecture must remain extensible").
