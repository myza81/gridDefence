# ADR-000: Architecture Principles

- **Status:** Accepted
- **Date:** 2026-07-01
- **Governing standard:** [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1

---

## Context

GridDefence is intended to operate as the engineering source of truth for transmission grid defence schemes for many years, across many contributors — human and AI — and many future modules (SPS/RAS, Black Start, Islanding, Restoration Planning, Network Analytics, and others per CLAUDE.md §27). Without a ratified, durable set of architecture principles, each new module or contributor would need to re-derive first principles independently, and inconsistencies would compound over time.

CLAUDE.md already defines these principles (§4 Engineering Philosophy, §5 Core Engineering Principles, §7 Domain Hierarchy). CLAUDE.md A13 requires that any change affecting core architecture, domain ownership, versioning, security, or database standards be recorded as an ADR. This ADR is the anchor record: it formally ratifies the foundational principles already established in CLAUDE.md as the accepted architecture baseline, so that every subsequent ADR, module architecture document, and implementation decision has a single decision record to trace back to.

This ADR does not introduce new principles. It formalizes the ones already active in CLAUDE.md v1.1.

---

## Decision

GridDefence adopts the following as its ratified core architecture principles. These principles govern every module, present and future, and take precedence over implementation convenience.

### Core Architecture Principles

1. **Engineering Truth Before Software Convenience.** The software models a real transmission network. Where software convenience conflicts with engineering correctness, engineering correctness wins. The system exists to support engineering decisions, not to simplify them. (CLAUDE.md §4)

2. **Single Source of Truth.** Every engineering entity has exactly one owner. Other modules reference it; they never duplicate it. Reference is always preferred over replication. (CLAUDE.md §5.1)

3. **Immutable Engineering History.** Approved engineering records are immutable. Historical records are never overwritten. Corrections create new versions. History is preserved permanently. (CLAUDE.md §5.2)

4. **Explicit Architecture.** Every business rule has a clearly defined owning module. Implicit behaviour is discouraged; hidden side effects are prohibited. (CLAUDE.md §5.3)

5. **Auditability.** Every engineering change is traceable: who, when, why, and what changed. (CLAUDE.md §5.4)

6. **Deterministic Behaviour.** The same engineering input always produces the same engineering result. Hidden automation that silently changes engineering decisions is avoided. (CLAUDE.md §5.5)

7. **Domain Hierarchy and One-Way Dependency.** Engineering data flows through a defined hierarchy (Master Data → Reference Data → Network Data → Scheme Data → Operational Data → Audit Data → Reporting & Analytics). Dependency flows from dependent domains toward the foundational domains they rely on, never the reverse. (CLAUDE.md §7, refined by A2)

8. **Domain Ownership.** Every engineering entity belongs to exactly one module. That module owns its identity, its business rules, and its audit trail. Other modules reference it by stable identifier; they never own or duplicate its data. (CLAUDE.md §8, A4)

9. **Architecture Precedes Implementation.** Architecture is documented and reviewed before code is written. This document takes precedence over any conflicting design until an ADR formally supersedes it. (CLAUDE.md §1, §24)

---

## Consequences

**Positive:**
- Every future module (and every AI agent contributing to it) has a single, unambiguous set of first principles to build against, reducing architectural drift across a multi-year, multi-contributor project.
- Immutability and auditability, established as ratified principles rather than optional practices, make GridDefence viable as a regulatory/compliance-grade system of record for grid defence engineering.
- One-way dependency and domain ownership keep the codebase splittable into services later without having to first untangle years of accumulated coupling.

**Negative / trade-offs:**
- These principles impose real overhead: every versioned entity requires a lifecycle implementation (see ADR referencing CLAUDE.md A3), every module requires its own audit trail (CLAUDE.md A4), and every new module requires an architecture document before implementation begins (CLAUDE.md §24). This is a deliberate trade of short-term implementation speed for long-term integrity.
- Strict domain ownership means some conveniences common in smaller CRUD systems — e.g. denormalizing a name field into a foreign table for a quick join — are disallowed by default (CLAUDE.md §5.1, §11.4).

---

## Alternatives Considered

1. **No formal, ratified principles — rely on informal team norms.** Rejected. With multiple human and AI contributors (CLAUDE.md §23) working across a project with a multi-year horizon, informal norms drift quickly and inconsistently; a ratified reference is needed for every contributor to converge on the same rules.

2. **Adopt an off-the-shelf generic enterprise architecture framework (e.g. TOGAF-style governance) wholesale.** Rejected. Such frameworks are process-heavy and not shaped around this platform's specific correctness and auditability requirements (engineering immutability, per-module audit ownership, deterministic engineering outcomes). A purpose-built, minimal principle set serves GridDefence better than a generic framework.

3. **Let architecture emerge from implementation ("code first, document later").** Rejected. This directly contradicts Engineering Truth Before Software Convenience (CLAUDE.md §4) and the mandated development lifecycle (CLAUDE.md §24), which requires architecture review before implementation begins.
