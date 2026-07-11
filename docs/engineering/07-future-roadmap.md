# GridDefence Future Roadmap — Core Platform and Supporting Modules

This document separates GridDefence's present and future capabilities into two categories — **Core Platform** and **Supporting Modules** — and explains why that separation must be preserved as the system grows. It does not schedule when any future capability will be built; it establishes which category any future capability belongs to, so that decision is never made ad hoc.

---

## 1. The Two Categories

```
┌───────────────────────────────────────────────────────────┐
│                      CORE PLATFORM                          │
│                                                               │
│   Registries  →  PSS/E Integration  →  Scheme Management    │
│                          │                     │              │
│                          ▼                     ▼              │
│                     Validation  ◄──────  Version Control     │
│                                                               │
│           (this is where engineering truth lives)            │
└──────────────────────────────┬────────────────────────────────┘
                               │  read-only
                               ▼
┌───────────────────────────────────────────────────────────┐
│                    SUPPORTING MODULES                        │
│                                                               │
│  Reporting   Dashboard   Heatmaps   Analytics                │
│  Historical Comparison   Statistics   Audit Summaries         │
│                                                               │
│        (this is where engineering truth is consumed,          │
│                    never originated)                          │
└───────────────────────────────────────────────────────────┘
```

Every arrow between the two boxes points one way, downward — from Core Platform to Supporting Modules. No Supporting Module capability ever feeds back into, or is required by, the Core Platform.

---

## 2. Core Platform

The Core Platform is where GridDefence's engineering truth is created, curated, and governed. Everything in it is authoritative.

### Registries

The engineering knowledge layer: the Substation Registry, Equipment Registry, Line Connectivity Registry, Relay Registry, and Sensitive Customer Registry (see **Engineering Knowledge** in [02-engineering-concepts.md](02-engineering-concepts.md)). Registries answer "what exists, and what do we know about it" — the slow-changing foundation everything else in the platform is built on. Line Connectivity Registry and Equipment Registry's transformer-asset records answer that question for identity and engineering metadata only (bay/breaker numbers, line type, commissioning dates); they do not answer "what is currently connected to what" — that is Operational Snapshot's role, below.

*Of these, Substation Registry, Equipment Registry, Relay Registry (implemented as the Automatic Load Shedding Functionality Registry, [ADR-011](../adr/ADR-011-automatic-load-shedding-functionality-registry.md)), and Sensitive Customer Registry ([ADR-012](../adr/ADR-012-sensitive-customer-registry-architecture.md)) are all built. This document's own scope is categorical, not a schedule (§ above) — see [implementation-plan.md](../architecture/implementation-plan.md) for build status and sequencing.*

### PSS/E Integration

The operational context layer: importing, versioning, and correlating PSS®E network topology and load snapshot data against the Registries (see **Operational Context**). This is how GridDefence stays current with the real, evolving network without ever confusing that currency with engineering authority. The resulting **Operational Snapshot** is authoritative for current electrical topology, connectivity, and operational bus/branch/transformer/load/generator state; the Registries above remain authoritative for identity and metadata. GridDefence correlates the two — neither overwrites the other.

### Scheme Management

The engineering decisions layer: Grid Defence Schemes, their Stages and Shedding Actions, and the Scheme Lifecycle that governs how a Working Draft becomes a Published Scheme and, eventually, an Archived Scheme. This is the platform's actual deliverable — everything else exists to support it.

### Validation

The continuous comparison of Published Schemes against current Operational Context, producing engineering-impact findings for engineers to act on (see [06-validation-philosophy.md](06-validation-philosophy.md)). Validation is Core Platform, not a Supporting Module, because it directly protects the integrity of Scheme Management's own output — a scheme nobody is checking against reality is not a trustworthy scheme.

### Version Control

The mechanism underlying both Scheme Management (the Scheme Lifecycle) and, separately, PSS/E Integration (topology and snapshot versioning) — ensuring every engineering decision and every operational reference is traceable, reproducible, and never silently overwritten (see [05-design-principles.md](05-design-principles.md), Principles 4, 5, and 7).

**Together, these five capabilities are what make GridDefence an authoritative engineering system of record, not a reporting tool with an opinion.**

---

## 3. Supporting Modules

Supporting Modules make the Core Platform's information more useful to consume — for engineers, for management, for auditors — without ever becoming a second place engineering truth could live.

### Reporting

Structured, formatted output of Core Platform information for a specific audience or purpose — a scheme summary, a compliance export, a stage listing. A report is always a *presentation* of existing engineering fact, never a new one.

### Dashboard

A composed, at-a-glance view aggregating information from multiple Core Platform sources — for example, current scheme status alongside recent validation findings. A dashboard answers "what does the current picture look like," entirely from data the Core Platform already owns.

### Heatmaps

A visual representation of network load or shedding coverage, derived from PSS/E Integration's load data and Scheme Management's assignment data. A heatmap is a derived visualization — it never becomes the record of what was actually assigned or actually loaded.

### Analytics

Derived insight computed from Core Platform history — trends, distributions, comparative statistics across schemes or time periods. Analytics may reveal something worth an engineer's attention, but the revealing is where its role ends; any resulting action is, once again, an Engineering Decision made through the Core Platform.

### Historical comparison

Comparing two points in a scheme's or the network's history — for example, "how has this scheme's Stage 1 changed over its last three Published versions." This is possible precisely because Version Control (Core Platform) already preserves that history; Historical Comparison only presents it.

### Statistics

Aggregate, numerical summaries drawn from Core Platform data (e.g. total MW currently assigned across all Published Schemes). Like Analytics, statistics are a read-only lens on existing fact.

### Audit summaries

A curated, readable presentation of the Core Platform's own audit and metadata records, for review or compliance purposes. This is not a separate audit mechanism — the underlying audit records themselves are owned and produced entirely by the Core Platform capabilities they describe.

---

## 4. Why Supporting Modules Must Never Influence Core Architecture

Three reasons, each sufficient on its own:

**1. A second source of truth is a correctness risk, not a convenience.** If a Dashboard or Analytics module were ever allowed to compute its own version of "what the scheme currently says" instead of reading it from Scheme Management, the platform would have two possible answers to the same engineering question, with no principled way to know which one is right when they disagree. [05-design-principles.md](05-design-principles.md) Principle 11 exists specifically to prevent this.

**2. The Core Platform must remain independently correct.** Every Core Platform capability — Registries, PSS/E Integration, Scheme Management, Validation, Version Control — must work completely and correctly on its own, with zero Supporting Module in existence. If a Core Platform capability ever needed a Supporting Module to function (for example, if Validation depended on Dashboard to display a finding before the finding could be considered "raised"), the boundary between the two categories would have already collapsed.

**3. Supporting Modules should be free to evolve quickly, without engineering risk.** Reporting formats change, dashboard layouts change, new visualizations get added and removed, as the platform's users' needs evolve. None of that churn should ever be able to touch the authoritative engineering record. Keeping Supporting Modules strictly downstream and read-only means they can be iterated on freely — even discarded and rebuilt — without any risk to engineering integrity.

---

## 5. A Simple Test for Any Future Capability

When a new capability is proposed, ask one question: **does it need to write new engineering fact, or does it only need to read and present existing engineering fact?**

- If it needs to write — a new kind of registry entry, a new kind of scheme content, a new validation check — it belongs in the **Core Platform**, and its design must go through the same architecture-first process as every other Core Platform capability (see `docs/architecture/README.md`).
- If it only needs to read and present — however sophisticated the presentation — it belongs in **Supporting Modules**, and can be built, changed, or removed without any corresponding change to the Core Platform's own architecture.

This test is deliberately simple, and deliberately strict. A capability that seems to need "just a little bit" of write access to be useful is a signal to reconsider whether it is really a Supporting Module at all, not a signal to make an exception.
