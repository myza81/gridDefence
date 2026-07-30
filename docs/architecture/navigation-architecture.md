# GridDefence Navigation Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15 Frontend Standards, A1 Module Communication, A12 Frontend Calculation Boundary, F4 Identity & Access Management, F6 Read-Only Join Trade-Off). Inherits from the [Application Shell Architecture](application-shell-architecture.md); aligns with the [UI/UX Philosophy](ui-ux-philosophy.md) and [Design System Philosophy](design-system-philosophy.md); subordinate to the [Engineering Philosophy](../engineering/01-engineering-philosophy.md).

Related: [engineering-workspace-architecture.md](engineering-workspace-architecture.md); [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md); [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md); [iam-module.md](iam-module.md).

**This is the navigation counterpart to the Application Shell Architecture, not a navigation design.** It defines how engineers reach, orient within, and move between engineering work — as responsibilities, concepts, boundaries, and growth principles. It prescribes no sidebar, menu, breadcrumb, tab, route, icon, or visual form; those are downstream and may change without changing this document. It also does not catalogue today's menu.

---

## 1. Purpose and Position

The [Application Shell](application-shell-architecture.md) establishes the continuous frame; **navigation is the movement within it.** Where the shell carries context, hosts workspaces, and maintains awareness, navigation is how an engineer *reaches* a destination and *understands where they are* once there.

Navigation exists to serve the platform's defining experience: GridDefence as **one connected engineering environment** ([UI/UX Philosophy](ui-ux-philosophy.md) §4), not a collection of modules. It must support two motions equally — **deliberate** movement to a known destination, and **investigative** movement through connected engineering knowledge ([UI/UX Philosophy](ui-ux-philosophy.md) §5) — and it must do both without ever requiring the engineer to understand the software's internal module boundaries.

The organising commitment of this document: **navigation follows engineering meaning, not software structure.** That the platform is internally modular ([CLAUDE.md](../../.claude/CLAUDE.md) §6) is an implementation fact the engineer should never have to learn in order to move through their work.

## 2. Navigation Principles

These hold regardless of how many capabilities the platform grows to contain.

1. **Navigation follows engineering meaning, not module boundaries.** It is organised around how engineers work — objects, domains, relationships, investigations — never around backend packages or table ownership.
2. **Navigation moves; it does not compute or decide.** It reaches where engineering state can be viewed or changed; it never derives an engineering result, relationship, or conclusion of its own (CLAUDE.md A12; [EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md)).
3. **Navigation follows authoritative identity.** Movement uses stable, authoritative object identities (CLAUDE.md §11.1); names, mnemonics, bus names, and breaker numbers assist *discovery* but never silently become *identity* (§ Engineering Constraints).
4. **Navigation never changes engineering state implicitly.** Reaching a location activates nothing, selects nothing, resolves nothing (§8).
5. **Navigation preserves orientation.** At every point the engineer can tell where they are, what is active, and how to return (§9).
6. **Navigation uses authoritative relationships; it never manufactures them.** A path exists only because the owning domain asserts the relationship (§6).
7. **Navigation reflects access; it does not decide it.** IAM and the owning domains remain authoritative (§14).
8. **Navigation fails honestly.** When a destination cannot be reached, it says so and preserves orientation rather than inventing a substitute (§16).

## 3. Concepts and Responsibilities

### What navigation is responsible for

- **Destination discovery** — helping an engineer find where to work, by domain, by object, by search, or by prior activity.
- **Orientation** — making current location, active object/workspace, owning domain, and active context legible (§9).
- **Movement** — between domains, between related engineering objects, and into and between workspaces.
- **Context-preserving transitions** — carrying appropriate context across a move, visibly and deterministically (§8).
- **Return paths and history** — letting non-linear investigation retrace and resume (§10).
- **Deep linking** — making meaningful engineering locations directly addressable and shareable (§11).
- **Entry into investigation** — turning a relationship into a followable path (§6, §12).

### What navigation must not own

- **Engineering data, truth, or relationships** — owned by the modules; navigation reflects, never holds, and is never a second source (F6).
- **Lifecycle rules, business logic, engineering judgement** — owned by the domains.
- **Authorization decisions** — owned by IAM (§14).
- **Workspace-specific state and module-specific operations** — owned by the workspace and its module (§12, §18).

Navigation may *reflect* permissions and availability; IAM and the owning modules remain authoritative for both.

## 4. The Navigation Model

The enduring model distinguishes a few **kinds of navigational target**, deliberately defined as concepts rather than as a fixed catalogue of today's modules:

- **Engineering domains** — broad areas of engineering work an engineer enters (§5).
- **Engineering objects** — the substations, transformers, buses, schemes, findings, snapshots the engineer actually reasons about (§6).
- **Workspaces** — where work on domains and objects happens, hosted by the shell (§12).
- **Prior activity** — recents and history: where the engineer has been (§10).
- **Saved locations** — deliberately pinned entry points into investigation (§10).

**What is architectural and what may evolve:** the *distinction* between reaching a domain, an object, a workspace, and one's own prior/saved activity is architectural and should endure. The *specific* domains, objects, and capabilities that populate each are expected to change continuously and are **not** part of this architecture. "Tasks" as a distinct navigational kind was considered and rejected — it folds into two better-owned concepts: **responsibilities** (owned by IAM/domains, surfaced as awareness — §14) and **saved locations** (§10). Navigation should not grow a task-management model of its own.

## 5. Domain Navigation

GridDefence contains related but distinct **engineering domains** — for example Engineering Registry, Network Representation, Defence Schemes, Continuous Evaluation, Reporting and Audit, and domains not yet conceived.

An **engineering domain is not an implementation module.** A domain is an area of engineering work as an engineer conceives it; a module is a unit of software ownership. They may align, but navigation is organised by the former. One domain may be served by several modules, and a single module may contribute to more than one domain — navigation must be free to present engineering domains that do not map one-to-one onto backend packages or database ownership. Domain navigation is therefore a **curated engineering map of the work**, not a rendering of the system's internal structure.

## 6. Engineering Object Navigation

Engineers navigate through **connected engineering objects** at least as often as through domain categories — substation → voltage yard → transformer → terminal → breaker; substation → correlated PSS®E bus → topology → load; scheme → stage → assignment → equipment; finding → affected object → source data → history.

Navigation's responsibility is to make these **relationship-driven movements** first-class:

- **A relationship that exists in the engineering model should not be a navigational dead end** — unless access (§14) or data availability (§16) genuinely prevents continuation. Continuity of the connected environment ([UI/UX Philosophy](ui-ux-philosophy.md) §4) is largely delivered here.
- **Navigation uses authoritative relationships only.** A path from a transformer to an LV voltage yard exists only because the owning engineering logic has established that association — never because navigation inferred it from a shared name, proximity, or convenience (§ Engineering Constraints). The distinction is not cosmetic: a manufactured relationship is navigation asserting an engineering fact, which it must never do.
- **Relationships are resolved from the owning domain at the time of movement**, so navigation reflects current authoritative associations rather than a cached guess.

## 7. Global Search as Navigation

Global search is an Application Shell service ([Application Shell Architecture](application-shell-architecture.md) §6). From navigation's perspective it is a **discovery entry point**: the engineer names an engineering object — substation, circuit, transformer, relay, bus, snapshot, scheme, report, finding — and search routes them to it. Its architectural relationship with navigation:

- **Search discovers; navigation moves; the domain owns.** Search resolves candidates from the owning modules (a shared read model is acceptable, F6) and hands an authoritative identity to navigation, which performs the move. Search is never a second registry, an alternative source of truth, or an engineering reasoning engine.
- **Results are grouped by engineering meaning** — by object kind and owning domain — so an engineer reads results the way they think, not as an undifferentiated list.
- **Ambiguity is surfaced, never resolved by guessing.** Duplicate or similar engineering identifiers — two objects sharing a mnemonic, a reused bus name across snapshots, a name that changed over time — must be presented as distinct authoritative identities with enough disambiguating context to choose. Navigation must never silently pick one, because names are not identity (§ Engineering Constraints).
- **Results may be context-aware** — where an active context makes some results more relevant, search may reflect that — but relevance ordering must never *hide* an authoritative match in a way that misrepresents what exists.
- **Search continues into relationships.** Arriving at an object via search leaves the engineer able to follow its relationships onward (§6) — a discovery entry point, not a terminus.

## 8. Context-Preserving Navigation

Engineers work within active context — a selected snapshot, a scheme version, a registry version, a comparison baseline, an evaluation scope, a selected substation, a geographic area. The shell carries this context ([Application Shell Architecture](application-shell-architecture.md) §3); navigation decides how it travels across a move.

The governing rules:

- **Preserve context when it remains meaningful** at the destination — moving from a table to a map of the same snapshot should not drop the snapshot.
- **Require a deliberate change when the destination needs a different context** — navigation surfaces the change as an explicit engineering act, never performs it silently.
- **Discard context when it does not apply**, visibly, rather than carrying a stale scope that would misrepresent the destination.
- **Never silently carry context into a destination where it changes engineering meaning unexpectedly.** Any context that materially affects displayed data or interpretation must remain **visible and deterministic** ([01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §10; [UI/UX Philosophy](ui-ux-philosophy.md) §6).
- **The owning domain validates whether a context applies.** Navigation proposes; the domain disposes. Navigation must not itself decide that a snapshot is valid for a scheme, or that a baseline is comparable — it asks the authoritative domain and reflects the answer.

## 9. Orientation and Location Awareness

At any point an engineer must be able to understand: **where they are**, **what object or workspace is active**, **what wider domain it belongs to**, **what active context affects it**, **how they arrived**, **how to return**, and **what related paths are available**.

This section defines the **information that must remain available**, not its visual form. Whether orientation is expressed as a trail, a header, a panel, or a form not yet invented is a design decision ([Design System Philosophy](design-system-philosophy.md)); the *architecture* requires only that these seven pieces of orienting information never become unavailable. Orientation is the antidote to the "lost in a large system" failure that growth otherwise causes — and it is what lets investigative, non-linear movement stay coherent rather than disorienting.

## 10. History, Recents, and Saved Locations

Engineering investigation is non-linear ([UI/UX Philosophy](ui-ux-philosophy.md) §5): an engineer may pass through many objects, workspaces, snapshots, and findings before returning to an earlier point.

Navigation supports this through three architecturally distinct concepts:

- **Navigation history and return paths** — a *temporary*, session-scoped trace enabling retrace and resume. A convenience, never an engineering record.
- **Recents** — recently visited objects and recently used workspaces, easing return to active lines of work. Also temporary and convenience-only.
- **Saved / pinned locations** — *deliberately* retained entry points into investigation. These carry intent, but they remain navigational bookmarks — not engineering evidence.

The essential discipline: **none of these is an authoritative engineering record.** History, recents, and favourites are navigational aids owned by navigation; the audit trail, the version history, and the finding record are owned by the domains ([CLAUDE.md](../../.claude/CLAUDE.md) A4) and are the only authoritative account of what happened. A saved location that points at an object which later changes lifecycle state must resolve to the object's *current* authoritative state (§15), never to a remembered snapshot of it.

## 11. Deep Linking and Shareable Locations

Collaborative work and auditability require that **meaningful engineering locations be directly addressable** — an object, a specific version, a workspace, a snapshot, an evaluation result, a scheme assignment, a comparison, or a scoped view where the scope is meaningful and reproducible.

Architectural requirements:

- **A deep link is a reference to authoritative engineering identity plus explicit context** — not a capture of hidden local state. A link whose meaning depends on state only the originating session held is not shareable and not auditable.
- **Reproducible scope must be explicit in the link**, so that a scoped or filtered view resolves the same way for another engineer, or the same engineer later — otherwise the scope is not meaningful, only incidental.
- **Deep links fail safely.** When a target no longer exists, is archived, has changed lifecycle state, is inaccessible, references a retired version, or requires unavailable context, navigation resolves to an **honest failure state that preserves orientation** — it states what happened and offers authoritative alternatives where they exist. It never silently substitutes a different object, and it **never reinterprets missing or changed engineering data** to make the link appear to still work (§15, §16).

## 12. Cross-Workspace Navigation and Coordination

A navigation action in one workspace frequently leads into another — selecting a substation on a map may let the engineer open its record, inspect connected equipment, view correlated PSS®E buses, open topology, review scheme assignments, or inspect findings.

Navigation enables these transitions **through shared identifiers and shell-mediated context, never through direct workspace-to-workspace dependencies** (mirroring CLAUDE.md A1 in the frontend; consistent with [Application Shell Architecture](application-shell-architecture.md) §5). Concretely:

- A navigation action carries an **authoritative object identity and explicit context** to the shell; the target workspace opens against that identity and resolves its own data from its own module.
- No workspace imports another's internal state or implementation, and no workspace depends on another's presence — a transition target that is absent degrades to an honest unavailable state (§16), not a broken caller.
- Coordination is **opt-in and loosely coupled**: navigation offers the path; workspaces are free to participate or not.

This keeps cross-workspace movement rich while preserving the module boundaries the whole platform depends on. It also supports **multiple concurrent or related workspaces** without coupling them: they share identity and context through the shell, not through each other.

## 13. Navigation Hierarchy and Growth

The platform may eventually hold dozens of capabilities. Navigation must grow **without** infinitely deep menus, oversized flat lists, frequent reorganisation, reliance on engineers memorising software structure, or exposing every capability at once.

The architecture does **not** fix a number of navigation levels. Instead it holds a principle: **hierarchy is justified only where it reflects genuine engineering structure, and discovery should be plural.** No single mechanism should bear the whole weight of a growing platform — domain grouping, contextual discovery (relevant paths surfaced from where the engineer already is), search, recents, and object relationships are **complementary**, and each new capability should be reachable by more than one of them. Depth is added when engineering meaning is genuinely nested; it is never added merely because the module count grew. The measure is constant: an engineer should reach relevant work by *meaning* — searching, following a relationship, entering a domain, resuming recent work — not by recalling where in a tree the software filed it.

## 14. Role and Permission Awareness

Engineers differ in responsibilities and permissions. Navigation reflects what a user can access while avoiding misleading absence.

- **Navigation reflects access; IAM and the domains decide it** ([iam-module.md](iam-module.md); CLAUDE.md F4). Hiding a destination is a *presentation* choice, never an authorization mechanism.
- **Hiding is not authorization — avoid security-through-obscurity.** Access must be enforced authoritatively at the domain/IAM boundary regardless of whether navigation shows or hides a path; navigation visibility is convenience, not a control.
- **Absence must not create misleading engineering meaning.** Where appropriate, an existing-but-inaccessible destination should be distinguishable from a non-existent one, so that a hidden path is not misread as an engineering fact — "you cannot see this here" is not the same statement as "there is nothing here."
- **Read-only access, unavailable operations, and assigned review/approval responsibilities** are reflected as availability and awareness ([Application Shell Architecture](application-shell-architecture.md) §7), never as navigation-owned rules.
- **Permission changes during a session** are reflected honestly: navigation must not rely on a stale permission picture, and a now-forbidden action must fail authoritatively at the domain boundary, not merely disappear from view.

## 15. Navigation and Lifecycle

Many GridDefence objects are versioned and lifecycled — draft, active, archived, superseded, entered-in-error, historical versions ([CLAUDE.md](../../.claude/CLAUDE.md) A3; [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)).

Navigation must **preserve lifecycle meaning**:

- Movement between current and historical records, active and draft versions, superseded objects, and archived evidence must keep **which state the engineer is looking at unambiguous**.
- **Navigation must never make two lifecycle-distinct objects appear interchangeable** because they share a name, mnemonic, or identifier. A superseded version and its active successor are different engineering records; navigation that conflated them would be asserting an engineering falsehood.
- **Lifecycle state is resolved from the owning domain**, so navigation reflects the object's *current* authoritative state and never presents a remembered or inferred state (§10, §11).
- Historical and archived records remain reachable — they are queryable engineering evidence (CLAUDE.md §11.6, A3) — and navigation must reach them *as history*, clearly distinguished from current records.

## 16. Failure and Partial Availability

Navigation must stay usable when parts of the platform are not.

- **A failure in one workspace or navigation service must not collapse the shell** ([Application Shell Architecture](application-shell-architecture.md) §4). Orientation and the ability to move elsewhere survive a local failure.
- When a destination module fails, a referenced object cannot load, search is unavailable, a workspace cannot restore, or related data is only partially available, navigation presents an **honest failure state** — what is unavailable, and what remains reachable — and preserves the engineer's orientation.
- **Navigation invents no substitutes.** It does not fabricate a relationship, a stand-in object, or a plausible-looking result to paper over missing data — an honest gap is correct; a manufactured continuity is a fabrication of engineering meaning ([EDR-006](../engineering/edr/EDR-006-operational-context-visualization.md)).
- Partial availability is reflected as partial, never rounded up to a false whole.

## 17. Extensibility

Future capabilities — geospatial awareness, topology exploration, advanced comparison, collaborative review, investigation collections, automated analysis, future registries and schemes, technologies not yet chosen — must integrate **without redesigning navigation**.

The enabling qualities, all technology-neutral:

- **Semantic destinations** — navigation targets are defined by engineering meaning and stable identity, not by knowing each capability by name.
- **Domain-owned navigation contributions** — a domain contributes its own destinations, relationships, and searchable objects into the shared navigation model; navigation composes them without being modified per capability.
- **Stable object references and shared identity contracts** — movement and deep links depend on durable identities every domain honours, so a new capability's objects are reachable and linkable from day one.
- **Context contracts** — context travels across a documented shape, so a new capability can participate in context-preserving navigation without navigation anticipating it.
- **Shell-mediated composition** — new capabilities join through the shell's roles and services ([Application Shell Architecture](application-shell-architecture.md) §8), never by wiring into navigation's internals.

The test of the architecture is the shell's own: navigation for three domains and navigation for thirty are the *same* navigation — capabilities are *composed in*, not *redesigned around*.

## 18. Boundaries and Decision Tests

Adjacent responsibilities, each owning a distinct concern:

- **Application Shell** — the continuous frame and its services; owns *continuity*. Navigation is one shell responsibility, scoped to *movement and orientation*.
- **Navigation** — reaching destinations and orienting within them. Owns no engineering data, truth, rules, or authorization.
- **Global Search** — a discovery-and-navigation service; resolves engineering objects and routes to them (§7). Not a registry, not a source of truth, not a reasoning engine.
- **Engineering Context** — the active working scope; carried by the shell, *travelled* by navigation, *owned* by the domains that define it.
- **Workspace** — where engineering work and its state live; navigation reaches it but never holds its state.
- **Context Panel / reflection** — reflects the active object and context; read-oriented, owns nothing.
- **Individual Module** — owns engineering data, relationships, lifecycle, rules, and audit.
- **IAM** — owns identity and authorization; navigation reflects, never decides.

**Decision tests** — for placing any navigation-adjacent concern:

1. **Reach-or-own?** Is this about *reaching or orienting within* engineering work (navigation), or about *owning* the work, data, or rules (a domain/workspace)?
2. **Continuous-across-workspaces?** Does it stay meaningful across many workspaces (shell/navigation), or is it specific to one kind of work (that workspace/module)?
3. **Move-or-change?** Does it merely *move to* where state can be viewed or changed (navigation), or does it *change engineering state* (the owning domain)?
4. **Second-source?** Would placing it in navigation create a second source of engineering truth or relationship? If yes, it belongs to the owning domain, and navigation may only reflect it.
5. **Reflect-or-decide?** For access and lifecycle: does navigation *reflect* an authoritative decision (allowed) or *make* it (forbidden — IAM/domain)?

If a concern changes state, owns truth, or decides access, it is not navigation's — navigation only ever *reaches* it.

---

## Engineering Constraints (Preserved)

- **Navigation follows authoritative engineering identity.** It uses stable, authoritative object identities wherever available. Names, labels, mnemonics, PSS®E bus names, breaker numbers, and display text may be ambiguous or change over time; they may assist discovery but must not silently become identity.
- **Navigation does not infer engineering truth.** It presents relationships supplied by authoritative domains. It must not calculate, assume, or manufacture a relationship to create a convenient path — for example, it must not decide which LV voltage yard belongs to a transformer unless that association has been established by the owning engineering logic.
- **Navigation does not change state implicitly.** Moving between locations must never silently activate a scheme, change a registry version, choose a snapshot, resolve a migration issue, approve an assignment, or change an engineering relationship. State-changing actions belong to the owning workspace and domain.
- **Navigation supports investigation without performing judgement.** It helps engineers reach evidence, context, history, relationships, and comparisons; it never decides the engineering conclusion for them.

## Final Principle

Navigation exists so that an engineer moving through GridDefence experiences **one connected engineering environment** — reaching any engineering object, domain, or workspace by *meaning*, orienting effortlessly, and following authoritative relationships wherever they genuinely lead.

Navigation reaches engineering work, and helps the engineer understand where they are within it.

It never owns that work, never manufactures a relationship, never changes state on its own, and never draws the engineering conclusion.

It moves the engineer to the evidence. The judgement remains, always, the engineer's.
