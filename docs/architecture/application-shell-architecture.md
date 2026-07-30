# GridDefence Application Shell Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (§15 Frontend Standards, A1 Module Communication, A12 Frontend Calculation Boundary, F6 Read-Only Join Trade-Off). Inherits from the [UI/UX Philosophy](ui-ux-philosophy.md) and [Design System Philosophy](design-system-philosophy.md); subordinate to the [Engineering Philosophy](../engineering/01-engineering-philosophy.md).

Related: [engineering-workspace-architecture.md](engineering-workspace-architecture.md); [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md); [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md); [iam-module.md](iam-module.md).

**This is the frontend equivalent of the system architecture, not a layout.** It defines the enduring structural responsibilities of the application shell — the frame every engineering workspace runs inside. It prescribes no screens, positions, geometry, or technology; those are downstream and may change without changing this document.

---

## The Shell Is Almost Invisible

The application shell exists to create **continuity**. Its highest measure of success is that engineers stop noticing it — that they feel they are moving through one connected engineering environment ([UI/UX Philosophy](ui-ux-philosophy.md) §4), not jumping between unrelated modules that happen to share a login.

A shell that draws attention to itself has failed in the same way decoration fails ([Design System Philosophy](design-system-philosophy.md) §2): it is spending the engineer's attention on the frame rather than the engineering. Everything below serves this: the shell is the stable, quiet continuity within which everything else changes.

Because it must remain stable across many years of module growth, the shell is defined by **responsibilities and roles**, never by fixed regions, positions, or a catalogue of the modules that exist today.

## 1. Shell Responsibilities

The shell owns the concerns that must be *continuous* — present and consistent no matter which workspace an engineer is in:

- **Navigation** — the means of moving between engineering destinations.
- **Engineering context** — carrying and reflecting what the engineer is currently working within (§3).
- **Global discovery** — a consistent way to find engineering objects (§6).
- **Global awareness** — an ambient view of the overall engineering environment (§7).
- **Identity** — reflecting who the engineer is and what they are responsible for, as owned by the IAM module. The shell *reflects* authorization — showing only what an engineer may reach — but never *decides* it; the authorization decision remains the IAM module's ([iam-module.md](iam-module.md)).
- **Workspace hosting** — providing the frame in which any workspace runs (§4).

"Engineering awareness," listed among these in early thinking, is deliberately *not* a separate widget the shell provides. Awareness is the shell's **purpose**, realised through context (§3) and global awareness (§7) — not a component to be placed somewhere.

**What explicitly does not belong to the shell:**

- **Engineering logic or computation.** The shell never computes an engineering result, never evaluates a scheme, never decides pass/fail (CLAUDE.md A12). It is a frame, not a module.
- **Ownership of workspace state.** Each workspace owns its own working state and its own backend interactions; the shell hosts it, it does not reach inside it.
- **Ownership of engineering truth.** The shell reflects data owned by modules; it never becomes a second source of it (F6 — the shell may present a read-model view, but the owning module remains authoritative).
- **Engineering business rules.** No validation rule, no publication gate, no lifecycle transition lives in the shell.

The shell is powerful precisely because it is narrow: it does the few things that must be everywhere, and nothing that belongs to a module.

## 2. Structural Regions

The shell is composed of a small number of **permanent structural roles**. Their *positions and geometry are not architectural* — a role may be realised as a bar, a panel, an overlay, or a form not yet invented, and may adapt to device or context, without changing the architecture.

The enduring roles:

- **A global-frame role** — persistent identity, global discovery, and global awareness; the things that never belong to any single workspace.
- **A navigation role** — the means of reaching engineering destinations (§9 distinguishes this from the frame).
- **An active-context role** — a continuously visible reflection of the engineering context the engineer is working within (§3).
- **A workspace host** — the region given over to the current engineering work, hosting any kind of workspace neutrally, and not assuming exactly one workspace is present at a time (§4).
- **An ambient-status role** — non-blocking awareness of background activity and environment state (§7).

Naming these as roles, not places, is what lets the shell's *layout* evolve for decades while its *architecture* stays fixed.

## 3. Engineering Context

Engineers are almost always working *within* something — a selected Operational Snapshot, a scheme, a registry version, a comparison mode, an evaluation scope. This context shapes what every workspace shows and means.

The shell's responsibility is to **carry and keep visible** the current engineering context, so that it persists coherently as the engineer moves between workspaces — moving from a table to a map should not silently drop the snapshot they were working in. Continuity of context is a large part of what makes the environment feel like one system rather than many.

Three disciplines keep this safe:

- **The shell reflects context; it does not own or compute it.** Authoritative context — which snapshot is Current, which Draft is user-scoped, what an evaluation scope resolves to — lives in the owning modules and in engineering state ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §5). The shell carries a *reference* to it and displays it faithfully.
- **Context must be explicit and visible, never an invisible global default.** A context that silently changes what an engineer sees — or changes an engineering result — without the engineer knowing would violate deterministic, honest presentation ([01-engineering-philosophy.md](../engineering/01-engineering-philosophy.md) §10; [UI/UX Philosophy](ui-ux-philosophy.md) §6). If context affects results, the engineer must be able to see the context that produced them.
- **Context changes are deliberate.** Switching snapshot, scheme, or scope is an intentional engineering act with visible consequence — never a hidden side effect of navigation.

## 4. Workspace Hosting

The shell hosts many *kinds* of engineering workspace — registry, map, dashboard, topology, analytics, comparison, reporting, and forms not yet imagined — and must treat them as **peers**. A map is not a lesser citizen than a table; a future workspace is not a lesser citizen than a current one.

The shell therefore provides *services* to workspaces — context, navigation, discovery, awareness, identity — but imposes **no internal structure** on them. It does not assume a workspace is a form, a grid, or a canvas. Each workspace decides its own internal shape, owns its own state, and talks to its own backend; the shell guarantees only the consistent frame around it. This neutrality is what allows entirely new kinds of engineering work to appear inside GridDefence without the shell needing to anticipate them.

The shell should not assume a *single* active workspace. One kind of engineering work may call for several workspaces present at once — a map beside a table beside a comparison — and the architecture must accommodate one or many without change. The host is a neutral region for the current engineering work, however many surfaces that work requires.

The shell should also preserve **workspace continuity** — incidental movement should not needlessly destroy in-progress work — while the workspace, not the shell, remains the owner of that state. And because the shell is the environment's continuity, a single failing workspace or unavailable module must not take the frame down with it: the shell remains stable and navigable so the engineer can move elsewhere, rather than losing the whole environment to one failure.

## 5. Cross-Workspace Coordination

Workspaces frequently cooperate. Selecting a substation might, in one moment, be reflected in a table, a context reflection, a topology view, and an evaluation summary at once.

The architectural rule is that this coordination happens through **shared engineering context and selection**, mediated by the shell — never through workspaces wiring directly into one another. Direct workspace-to-workspace coupling would recreate, in the frontend, exactly the boundary violation the backend forbids (CLAUDE.md A1); it would also make each workspace fragile to the others' existence.

Instead: a workspace publishes a change to shared selection/context; other workspaces *may* react to it. This keeps coordination **opt-in and loosely coupled**:

- A workspace that reacts to a shared selection enriches the experience.
- A workspace that ignores it is still entirely valid.
- No workspace depends on another being present, and none breaks when another is added or removed.

The shell provides the shared channel and the continuity; it never forces a workspace to participate, and it never becomes the place where cross-workspace *engineering logic* lives.

## 6. Global Search

Engineers think in engineering objects — a substation, a circuit, a transformer, a relay, a bus, a scheme. The shell provides one **consistent discovery mechanism** across all of them, always reachable, so that finding an object never depends on first knowing which module owns it.

The philosophy:

- **Search is discovery and navigation, not truth.** It resolves an engineering object and routes the engineer to it, in the workspace and module that own it — it never reimplements the object or becomes a second source of its data.
- **Search respects ownership.** Results are drawn from the owning modules (a shared read model is acceptable, F6); the shell does not become an authority over what it finds.
- **Search reinforces continuity.** Arriving at an object via search should carry appropriate context and leave the engineer able to follow its relationships onward — never a dead end ([UI/UX Philosophy](ui-ux-philosophy.md) §4).

Related: engineering objects and contexts an engineer reaches should be **addressable and shareable** — reachable again directly, not only through a remembered sequence of steps — which is itself part of a connected environment.

## 7. Global Awareness

The shell maintains an **ambient, non-blocking** view of the overall engineering environment — the things an engineer benefits from sensing without leaving their current work. Where §3 carries the *active context* that shapes the current work, awareness surfaces the broader *environment state* around it:

- a validation summary and unread engineering impacts;
- running imports and background analysis;
- what the engineer is responsible for across the environment.

What belongs here is *ambient status*, not *engineering action*. The distinction matters:

- **Awareness reflects; it does not decide.** The awareness surface points to findings and impacts; it never judges them, resolves them, or flags a pass/fail ([EDR-004](../engineering/edr/EDR-004-decision-support-not-automation.md)). "Three unread impacts" is awareness; "this scheme fails" is a judgement the shell must not make.
- **Awareness aggregates a read view; it does not own the data.** Findings are owned by the modules and governance that produce them ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)); the shell surfaces a summary and routes the engineer to the owning workspace to act.
- **Awareness is honest and calm.** It shows the real state of the environment without alarm inflation — consistent with a quiet engineering instrument ([Design System Philosophy](design-system-philosophy.md) §2, §6).

The shell makes the engineer *aware*; the workspace is where they *act*.

## 8. Extensibility

The shell must absorb capabilities no one has yet imagined — future maps, registries, dashboards, analytics, collaboration, and technologies — **without structural redesign**. The enabling principle is the same one the design language uses: **define roles and services, not a catalogue**.

- The shell knows about *kinds of participation* — something that can be navigated to, can host a workspace, can contribute to discovery, can contribute to awareness, can read and publish shared context — not about the specific modules that exist today.
- A new capability integrates by **fulfilling those roles**, not by the shell being modified to know it by name. There is no hardcoded list of modules, registries, or workspaces anywhere in the shell's architecture.
- Growth is therefore *composition*, not *redesign*: the shell that hosts three modules and the shell that hosts thirty are the same shell.

A shell built around today's known modules would need reworking for every new one. A shell built around durable roles grows to fit capabilities its authors never anticipated — the only property that ultimately matters for a platform expected to expand for years.

## 9. Boundaries

Each layer owns a distinct concern; overlap is the thing to prevent.

- **Application Shell** — the continuous frame: context-carrying, discovery, awareness, identity, and workspace hosting. Owns *continuity*. Owns no engineering data, logic, or rules.
- **Navigation** — the means of *movement* between destinations. It changes *where* the engineer is; it does not hold engineering state, and it is not itself the frame. (Navigation is a shell responsibility, but a narrow one — routing attention, not owning it.)
- **Workspace** — where engineering *work* happens. Owns its own internal state, its own interactions with its owning module's backend, and its own presentation. The shell hosts it but never reaches inside it.
- **Context reflection** — a shell-provided surface that *reflects* the current engineering context and selection. It is read-oriented and owns nothing; it shows what the modules and shared context already hold, distinct from the workspace's own primary work surface.
- **Individual Modules** — own engineering data, rules, truth, and audit (CLAUDE.md A1, A4). Everything above ultimately reflects or routes to them; none of it replaces them.

The single test for a boundary question: *does this concern need to be continuous across all workspaces?* If yes, it is the shell's. If it is specific to one kind of engineering work, it belongs to a workspace or its module — never to the shell.

## Final Principle

The application shell's success is measured by what the engineer does *not* notice.

It carries context, offers discovery, maintains awareness, and hosts every kind of engineering work inside one continuous environment — and then gets out of the way.

The shell creates continuity. The engineering happens within it, and the decision remains, always, the engineer's.
