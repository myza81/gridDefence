# GridDefence Architecture Documentation

This directory is the authoritative index of architecture documentation for GridDefence.

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) (v1.1). Where any document in this directory appears to conflict with CLAUDE.md, CLAUDE.md takes precedence unless an ADR has formally superseded it.

---

## 1. Document Index

| Document | Purpose | Owner |
|---|---|---|
| [system-overview.md](system-overview.md) | High-level architecture: bounded contexts, tech stack, module communication, dependency direction | Project Architecture |
| [domain-model.md](domain-model.md) | Conceptual domain model: domain hierarchy, domain groupings, entity ownership rules | Project Architecture |
| [substation-registry.md](substation-registry.md) | Module architecture for the Substation Registry (Master Data domain) | Substation Registry module owner |
| [../adr/](../adr/) | Architecture Decision Records — the append-only log of accepted architectural decisions | Project Architecture |

Module-specific architecture documents (e.g. `substation-registry.md`, future `ufls.md`, `uvls.md`, `emls.md`) each describe a single bounded context in depth. `system-overview.md` and `domain-model.md` describe the platform as a whole and do not duplicate module-level detail.

---

## 2. Recommended Reading Order

1. [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) — engineering principles and standards (mandatory first read for any contributor, human or AI).
2. [system-overview.md](system-overview.md) — how the system is structured and how modules are allowed to talk to each other.
3. [domain-model.md](domain-model.md) — what the domains are, what each owns, and how they relate.
4. The relevant module architecture document(s) for the area of work (e.g. [substation-registry.md](substation-registry.md)).
5. [../adr/](../adr/) — relevant Architecture Decision Records, for the historical "why" behind a standing rule.

Do not begin implementation on a module before its module architecture document exists and has been reviewed, per CLAUDE.md §24 (Development Workflow).

---

## 3. Document Ownership

- **System-level documents** (`README.md`, `system-overview.md`, `domain-model.md`) are owned by Project Architecture. Changes to these that alter a core principle (domain ownership, dependency direction, module communication, versioning, security) require an ADR per CLAUDE.md A13.
- **Module architecture documents** are owned by whoever owns that module's bounded context. A module document may be updated by its owner without an ADR, provided the change does not contradict a core principle in CLAUDE.md or an accepted ADR.
- **ADRs** are immutable once Accepted. A decision is changed only by superseding it with a new ADR, never by editing the original (mirrors CLAUDE.md §5.2, Immutable Engineering History, applied to the documentation process itself).

---

## 4. Adding a New Module Document

When a new module (e.g. UVLS, EMLS, SPS/RAS, Black Start) reaches the architecture stage:

1. Create `docs/architecture/<module-name>.md` using the Canonical Module Architecture Document Template defined in CLAUDE.md **A8**. This template is mandatory and replaces any earlier ad hoc checklist.
2. Add a row for the new document to the **Document Index** table in this README.
3. Confirm the module's place in the domain hierarchy and update [domain-model.md](domain-model.md) if the module introduces a new domain grouping (rather than fitting inside an existing one).
4. If the module introduces a new cross-cutting rule, a new dependency, or a deviation from an existing standard, raise an ADR under `docs/adr/` per CLAUDE.md **A13** before the module document is finalized.
5. The module document must not proceed to implementation until it has been reviewed per CLAUDE.md §24 (Development Workflow) and §25 (Definition of Done).

No module document may duplicate master data or scheme data owned by another module. Reference, don't replicate — per CLAUDE.md §5.1 and §11.4.
