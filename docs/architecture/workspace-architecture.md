# GridDefence Workspace Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§5.1 Single Source of Truth, §15 Frontend Standards, A1 Module Communication, A6 Domain Model Layering, A12 Frontend Calculation Boundary, A4 Audit Ownership, F4 IAM, F6 Read-Only Join Trade-Off). Inherits from the [Application Shell Architecture](application-shell-architecture.md) and [Navigation Architecture](navigation-architecture.md); aligns with the [UI/UX Philosophy](ui-ux-philosophy.md) and [Design System Philosophy](design-system-philosophy.md); subordinate to the [Engineering Philosophy](../engineering/01-engineering-philosophy.md).

Related: [engineering-workspace-architecture.md](engineering-workspace-architecture.md) (the scheme Draft-editing workspace — a **concrete instance** of this general architecture, not a competing definition); [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md); [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md); [ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md); [iam-module.md](iam-module.md).

**This is the working-environment counterpart to the Shell and Navigation architectures, not a layout, screen catalogue, dashboard, or component specification.** It defines the *engineering workspace* — its purpose, responsibilities, state, boundaries, behaviour, lifecycle, coordination, and extensibility — in technology-neutral terms. It prescribes no page, tab, pane, route, or visual form, and no current workspace catalogue.

---

## 1. Purpose and Lineage

The lineage is now four layers deep, and this document completes it:

- the **[UI/UX Philosophy](ui-ux-philosophy.md)** defines how engineers should *experience* GridDefence;
- the **[Design System Philosophy](design-system-philosophy.md)** defines how that experience is *visually expressed*;
- the **[Application Shell](application-shell-architecture.md)** defines the *continuous environment*;
- the **[Navigation Architecture](navigation-architecture.md)** defines *movement and orientation* within it;
- the **Workspace** — this document — defines *where coherent engineering activity occurs*.

The shell provides continuity. Navigation reaches and orients. **The workspace is where an engineer actually investigates, reviews, compares, edits, validates, or understands engineering information** — the focused engineering interaction the other layers exist to make possible.

## 2. What a Workspace Is

> **An engineering workspace is a bounded, coherent engineering activity — organised around an engineering purpose and one or more authoritative engineering objects — that composes domain capabilities and presentation surfaces into a single focused interaction, while owning none of the engineering truth it presents.**

A workspace is defined by **coherent engineering intent**, never by URL structure, backend ownership, or visual arrangement. "Maintain the substation registry," "investigate this evaluation finding," "compare two snapshots," "prepare this scheme version" are workspaces because each is *one engineering activity an engineer would name as such* — even when it spans several domains and surfaces.

A workspace characteristically has: a coherent engineering **purpose**; one or more authoritative engineering **objects** it is about; explicit working **context**; one or more **presentation surfaces**; its own **working and view state**; a set of **permitted engineering actions**; **lifecycle-aware** behaviour; and **entry and return** paths. Not all are mandatory — a read-only investigation may permit no actions — but purpose, at-least-one authoritative object or context, and orientation are the irreducible core.

**What is not a workspace.** A notification, a menu, a reusable panel, a modal, a navigation result, a passive metric, a background process, and a backend module are *not* workspaces — not because they are small, but because none is a *coherent engineering activity the engineer conducts*. Size and visual prominence are irrelevant: a single dense table maintaining a registry is a workspace; a full-screen dashboard that only routes elsewhere is navigation, not a workspace. The test is intent, not area.

**On workspace "families."** Registry, investigation, comparison, scheme-authoring, review, map, topology, evaluation, migration, and reporting workspaces are useful *descriptive* groupings — but this document deliberately declines to make them a **mandatory taxonomy**. Their architectural value is only that they hint at recurring *shapes*; every one of them is still just a workspace and must satisfy the same common contracts (§12). A fixed family catalogue would constrain future capability for no benefit, so families are illustrative, never structural.

## 3. Responsibilities and Non-Responsibilities

**A workspace owns:**

- the coherent engineering **interaction** for its purpose;
- **presentation** of domain-owned information (reflecting, never holding, authoritative truth);
- **local selection and filtering**, and workspace-specific **comparison choices** (view/working state);
- **user-entered working input** (draft values, tentative selections), subject to domain rules;
- **orchestration** of *permitted* domain actions — initiating them, never redefining them;
- **validation feedback**, loading/empty/partial/**failure** states;
- **restoring** its own meaningful working and view state (§9);
- **exposing related navigation opportunities** (handing identity + context to navigation, never wiring to another workspace).

**A workspace must not become:**

- a **second source of engineering truth** (CLAUDE.md §5.1) or an owner of another domain's data;
- an **authorization authority** (IAM decides — §10);
- a **replacement for domain lifecycle logic** or rules;
- a **hidden cross-module integration layer** — it consumes contracts, never another module's internals (CLAUDE.md A1);
- an **engineering-judgement engine** (EDR-004) or a manufacturer of relationships (EDR-006);
- a **permanent owner of shell-wide context** — it *uses* context the shell carries; it does not own it.

The workspace is powerful by composition and narrow by ownership: it brings many domains together into one activity precisely *because* it claims authority over none of them.

## 4. Workspace, Page, Module, and Surface

Four distinctions the architecture depends on:

- **Workspace vs page.** A *page* is a technical/visual delivery mechanism. A *workspace* is an engineering-intent concept that may span several surfaces, contain several views, address several objects, persist across navigation, and host multi-step activity. Whether a workspace appears as one screen, several, tabs, panes, routes, or windows is unspecified here.
- **Workspace vs module.** A *module* owns domain capabilities, rules, persistence, and contracts. A *workspace* composes *permitted* capabilities into an engineer-facing activity. One workspace may use several modules; one module may serve several workspaces. The workspace consumes **defined contracts** only — never another module's repository, internal state, or implementation. This is the no-cross-module-repository-import principle (CLAUDE.md A1) expressed at the frontend architectural level.
- **Workspace vs presentation surface.** A *surface* (table, map, topology, chart, timeline, form, comparison, history, context reflection, report view) is *one expression* of engineering meaning. A workspace may use several complementary surfaces around one purpose; no surface is universally dominant — the right surface follows the awareness or engineering question being served ([UI/UX Philosophy](ui-ux-philosophy.md) §3; [Design System Philosophy](design-system-philosophy.md) §5). Critically, **all surfaces in a workspace must reflect the same authoritative context** — a table, map, and topology view must never silently apply different filters, versions, or scopes while appearing to represent the same workspace (§6).
- **Workspace vs context panel.** A context panel *reflects* the active object/context in support of the current work; it is read-oriented and owns nothing. It is a shell/workspace-provided reflection, not an activity in itself.

## 5. State Ownership

The single most important discipline in this architecture is that **four kinds of state are never conflated**, because their owner and their restoration behaviour differ:

| State | What it is | Owner | Authoritative? | Restoration |
|---|---|---|---|---|
| **Engineering state** | Registered equipment, scheme assignments, lifecycle status, approved settings, persisted correlations, findings, historical versions | The owning **domain** | **Yes** | Re-fetched live and revalidated; never restored from the client |
| **Working state** | Draft input, pending edits, tentative selections, unresolved validation, comparison choices, an investigation path | The **workspace** coordinates it, subject to domain rules | No | Recoverable *locally* as convenience; is **not** persistence (§8) |
| **View state** | Filters, sort, grouping, expansion, zoom, visible columns, table position, selected layer | The **workspace** (presentation) | No | Freely restorable; carries no engineering meaning |
| **Shell context** | The active working scope continuous across relevant workspaces (§6) | The **shell** carries it; the **domain** validates it | Reflects domain truth | Re-validated on restoration, never assumed |

Two rules follow and are absolute: **view state and working state must never masquerade as authoritative engineering state**, and **a deliberately saved draft (an authoritative domain draft record) is a different thing from recoverable local working state** (§8). Confusing the two is how a platform silently loses or fabricates engineering data.

## 6. Engineering Context

Context — selected snapshot, scheme/version, registry version, comparison baseline, evaluation scope, selected substation/equipment, geographic area, lifecycle state, historical point — is *carried* by the shell and *transported* by navigation, but its **validity is decided only by the owning domain** ([Application Shell Architecture](application-shell-architecture.md) §3; [Navigation Architecture](navigation-architecture.md) §8).

A workspace's contract with context:

- It distinguishes **required** context (the activity is meaningless without it), **optional** context, **inherited** context (from shell/navigation), and **workspace-local** context (a scope the engineer sets within the activity).
- It **asks the owning domain whether inherited context applies**, and honours the answer — it never applies a shell context where the domain deems it invalid, and it never silently invents missing context.
- **Incompatible context fails deliberately and visibly**, offering a deliberate context change rather than a silent substitution.
- Any context that **materially affects interpretation or action must be visible and deterministic** ([01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §10; [UI/UX Philosophy](ui-ux-philosophy.md) §6) — the engineer can always see the scope that produced what they see.
- **Context change, reset, and restoration are explicit engineering acts** — never side effects of opening, navigating to, or restoring a workspace.

## 7. Selection, Composition, and Cross-Workspace Coordination

**Selection** is common but a frequent source of hidden coupling. A workspace may hold local selection, a primary object, multiple selected objects, and transient focus, and may use selection for navigation, editing, or comparison. The constraint: **a selected object is not an authoritative engineering relationship, and two objects shown or selected together are not thereby related.** Shared selection travels as **stable authoritative identity plus explicit context** (CLAUDE.md §11.1); a workspace must never infer an engineering association from co-display (EDR-006).

**Composition** is how a workspace presents several domains at once — e.g. a substation investigation showing registry data, connected equipment, PSS®E bus correlations, topology, loading, scheme assignments, findings, and history. The workspace **coordinates their presentation; it must not replicate or independently reconcile their authoritative truth** (CLAUDE.md §5.1, F6). Composition relies on: domain-provided **read models**; **stable identifiers**; **declared capability contracts**; **independent loading** so one slow/absent source does not block the rest; **ownership labelling** where provenance could be ambiguous (§10); and **safe degradation** (§11).

**Cross-workspace coordination** happens *only* through shared engineering context, shared stable identities, navigation destinations, shell-mediated selection, explicit comparison inputs, and published domain read models/events — **never through direct dependence on another workspace's internal state** (mirroring CLAUDE.md A1; [Application Shell Architecture](application-shell-architecture.md) §5). It must be **optional, explicit, and deterministic**: a map selecting a substation identity updates shell-mediated context; a topology workspace *may* respond; a registry workspace *may* offer navigation to the same identity — and any workspace that ignores it remains valid. Coordination that *changes what another workspace shows* should generally require **deliberate action**; only unambiguous, non-destructive context sharing is appropriate to propagate automatically. **Cascades — one selection silently reshaping several unrelated workspaces — are prohibited.**

## 8. Editing, Commands, and Unsaved Work

Some workspaces are read-only; others permit controlled change. The architecture separates a ladder of concerns, each with a distinct owner:

**navigation → selection → working-state change → validation → command → authoritative state change.**

The first four are workspace/presentation concerns. A **command** is where the workspace *initiates* an authoritative change (draft creation, save, submit-for-review, approval, activation, archive, enter-in-error, import acceptance). **The command's rule, eligibility, and effect are owned by the domain** ([ADR-010](../adr/ADR-010-engineering-decision-support-philosophy.md); CLAUDE.md A3, F5) — a workspace may invoke it but must never redefine it, and the domain remains responsible for conflict detection, stale-data rejection, and concurrent-change handling. **No implicit commands:** opening, navigating, selecting, restoring, or changing a view must never commit, approve, activate, correlate, resolve, or modify engineering state.

**Unsaved and incomplete work** must be classified honestly (per §5): *recoverable local working state* (a convenience) is not *a deliberately saved draft* (an authoritative domain draft record). Interruption may leave unsaved edits, incomplete forms, pending decisions, unresolved validation, temporary comparison state, unfinished investigation chains, or partially loaded data — the workspace may recover *local* state, but **local restoration never equals authoritative persistence**, and **leaving a workspace must never silently commit engineering changes.**

## 9. Restoration and Concurrent Workspaces

**Restoration.** A workspace may be newly opened, revisited, restored after interruption, opened from a deep link or recents, or reconstructed from a saved investigation — possibly after the underlying data changed. The rule is *restore the frame, revalidate the truth*: **engineering identity stays stable; applicable context is re-validated (§6); view state may be restored freely; authorization is rechecked (§10); lifecycle changes are reflected (§10); stale drafts are identified; missing historical records fail honestly (§11).** A workspace must **never recreate an earlier authoritative engineering state merely because its view state was restored** — restoring a filter is not restoring a fact.

**Concurrency.** The shell permits one or many workspaces ([Application Shell Architecture](application-shell-architecture.md) §4). Concurrent workspaces have **independent working and view state** and **share only shell-mediated context and stable identities**. A workspace requiring a different snapshot, version, or comparison scope **must not silently mutate another workspace's interpretation** — conflicting context requirements are held independently, surfaced to the engineer, never resolved by one workspace overwriting another's scope. Duplicate views of the same object must each reflect current authoritative state (avoiding one going stale unnoticed), and **a fault in one workspace must not collapse the shell or unrelated workspaces** (§11).

## 10. Comparison, Investigation, Lifecycle, Validation, Permissions, Audit

These are the concerns where "present, don't decide" matters most.

**Comparison.** A comparison workspace makes its subjects **explicit and identity-stable** (two snapshots, two versions, active-vs-draft, before-vs-after migration, current-vs-historical, expected-vs-imported, two areas), with **reproducible scope** and **visible context**. Missing/changed objects and lifecycle differences are shown honestly, not hidden. A comparison **may reveal differences; it must not declare the engineering conclusion** unless an authoritative domain evaluation explicitly provides one (EDR-004, EDR-006). Difference is evidence; significance is the engineer's, or an owning domain's.

**Investigation.** Investigation is non-linear and evidence-driven: following relationships, opening supporting evidence, preserving a path, returning, comparing sources, and (where such capability exists) saving entry points or notes. The workspace architecture **enables investigation without inventing an investigation domain** — GridDefence does not currently own formal case management, and this document does not create one. An investigation is a *workspace activity* over authoritative domain objects; any persistent "investigation record" would be a new domain requiring its own ADR, not something the workspace layer may quietly manufacture. Observed evidence must remain distinguishable from an engineer's own conclusions.

**Lifecycle and versions.** A workspace must preserve the distinctions between draft, submitted, approved, active, superseded, archived, entered-in-error, historical, imported-candidate, and accepted data (CLAUDE.md A3; [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)). It shows **which version is being viewed or edited**, keeps historical/superseded views clearly read-only-as-history, resolves lifecycle state live from the owning domain, and **never collapses lifecycle-distinct objects into one apparently-current record** because they share a name or identifier. Actions unavailable in a given lifecycle state are reflected as unavailable — by the domain's rule, not the workspace's.

**Validation and findings.** A workspace may present field validation, domain validation, migration issues, correlation uncertainty, continuous-evaluation findings, compliance results, warnings, and incomplete data. It must keep clear the difference between *validating input against a domain rule*, *presenting an authoritative evaluation result* the domain produced, *presenting evidence*, and *making a judgement* — and it must do only the first three (EDR-004, EDR-006; [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)). It never manufactures a conclusion.

**Permissions.** The workspace **reflects** read/edit access, review responsibility, approval authority, restricted data, and unavailable commands; **IAM owns authorization and the domain owns action eligibility** (CLAUDE.md F4; [iam-module.md](iam-module.md)). Hiding a control is not authorization. When permissions change mid-session, or restored state contains actions the user can no longer perform, the workspace reflects the change honestly and the **now-forbidden action fails authoritatively at the domain boundary**, never merely disappears.

**Audit and provenance.** A workspace composes many sources, so it must keep provenance **reachable and understandable where it affects engineering trust or auditability** — source domain, snapshot/version, lifecycle status, import source, effective date, last update, actor/process, and authoritative-vs-derived presentation. Not every item shows all metadata always; the requirement is reachability, not permanent display. **Workspace-local activity history is never a substitute for domain audit records** (CLAUDE.md A4).

## 11. Loading, Failure, and Scale

**Honest degradation.** A workspace depends on several independently-available capabilities. When one source fails, a relationship cannot load, a snapshot is incomplete, an analysis is running, stale data is detected, an import is pending, a module is unavailable, a surface fails, or restoration partially succeeds — the workspace **degrades honestly**: it shows what is available, marks the boundary of what is not, and **invents no substitute data and implies no completeness it does not have.** Absence of data is never presented as evidence of absence. A failure in one workspace must not collapse the shell or unrelated workspaces ([Application Shell Architecture](application-shell-architecture.md) §4).

**Scale as an architectural concern (not an optimisation spec).** Workspaces may face thousands of records, large networks, long histories, many snapshots, dense findings, and heavy visualisations. The enduring principles: **progressive disclosure** (overview first, detail on demand), **scoped loading**, **meaningful aggregation** with **explicit completeness**, **deterministic filters**, and a strict separation of overview from detail. The one inviolable rule: **a performance strategy must never silently alter engineering meaning** — an aggregate that omits data must say so; a truncated result must not look complete; a sampled view must not masquerade as the whole.

## 12. Extensibility and Workspace Contracts

**Extensibility.** New workspace types — advanced geospatial analysis, dynamic topology exploration, multi-snapshot studies, collaborative review, future schemes, relay coordination, sensitive-customer analysis, simulations, technologies not yet chosen — must integrate **without redesigning the shell or this architecture**. They integrate **semantically**, by *declaring*: engineering purpose; required domain capabilities; accepted context; produced/shared context; stable identities; restoration behaviour; lifecycle and permission requirements; and failure boundaries. This document describes semantic extensibility, not a plugin framework or registration API — the mechanism is a downstream decision.

**Common contracts.** Rather than an implementation interface, every workspace should honour a small set of **genuinely cross-workspace, enduring** commitments — the critiqued shortlist:

1. an **identifiable engineering purpose**;
2. **explicit applicable context** (§6);
3. **authoritative data ownership** left with the domains (§3, §5);
4. **stable identity** use (§7);
5. **lifecycle awareness** (§10);
6. **honest loading and failure** behaviour (§11);
7. **defined navigation entry and exit** (handing identity + context to navigation);
8. a **restoration policy** (§9);
9. an **unsaved-work policy** (§8);
10. **permission reflection** (§10);
11. **provenance reachability** (§10);
12. **fault isolation** (§9, §11).

Items proposed in early thinking but rejected from the contract list: "workspace-local audit history" (it is a convenience, never a contract — audit is the domain's, CLAUDE.md A4) and any "workspace registry of types" (that is extensibility mechanism, not an architectural contract). The twelve above are kept only because each is cross-cutting and durable; none is an implementation signature.

## 13. Boundaries and Decision Tests

Adjacent responsibilities, each owning a distinct concern:

- **Application Shell** — the continuous environment and its services (owns *continuity*).
- **Navigation** — reaching destinations and orienting (owns *movement*).
- **Workspace** — one coherent engineering activity (owns *the interaction and its working/view state* — no truth, rules, or access).
- **Context Panel** — reflection of active context for the current work (owns *nothing*).
- **Presentation Surface** — one expression of engineering meaning (owns *rendering*, not meaning).
- **Domain Module** — authoritative data, rules, lifecycle, operations, relationships (owns *truth*).
- **IAM** — authorization (owns *access decisions*).
- **Background Processing** — imports, evaluations, long-running execution (owns *asynchronous work and its results*).
- **Audit** — authoritative history and provenance (owns *the record of what happened*).

**Decision tests** for placing any workspace-adjacent concern:

1. **Purpose** — does it serve *one coherent engineering activity*? If yes, it may be a workspace concern.
2. **Truth** — does it *own* authoritative data, rules, lifecycle, or judgement? If yes, it belongs to a domain, not the workspace.
3. **Continuity** — must it remain present across *unrelated* workspaces? If yes, it may be the shell's.
4. **Movement** — is it about *reaching* another destination? If yes, it belongs to navigation.
5. **Surface** — is it only *one way of presenting* the same meaning? If yes, it is a surface within a workspace.
6. **State** — is the state authoritative, working, view, or shell context? Its class determines its owner *and* its restoration behaviour (§5).
7. **Coupling** — would it require one workspace to understand another's *internals*? If yes, the boundary is wrong.
8. **Silent-change** — could it change engineering meaning, context, or authoritative state *without deliberate engineer action*? If yes, reject or redesign it.

**Summary boundary rule** (in the spirit of Navigation's):

> A workspace composes and presents. If a concern owns truth, decides access, or changes engineering state without a deliberate engineer action, it is not the workspace's — the workspace may only reflect it, or initiate a command the domain owns.

## Final Principle

A workspace is where an engineer does one coherent piece of engineering work — bringing many domains, surfaces, and pieces of evidence together into a single focused activity, oriented and continuous within the shell.

It composes everything and owns almost nothing: not the truth it shows, not the rules it obeys, not the access it reflects, not the judgement it supports.

It gathers the engineering evidence into one place, and lets the engineer work.

The decision — as everywhere in GridDefence — remains the engineer's.
