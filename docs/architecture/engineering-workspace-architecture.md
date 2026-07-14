# Engineering Workspace Architecture

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A6, A8, A12). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

Related: [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md), [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md), [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md), [scheme-data-consumption-matrix.md](scheme-data-consumption-matrix.md), [engineering-review-panel-architecture.md](engineering-review-panel-architecture.md), [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md).

**Status update:** the continuous findings surface (§3, §6, below) and formal Publication review (§3, final bullet) are now given a concrete, first-class UX home — the [Engineering Review Panel](engineering-review-panel-architecture.md), which visualizes but does not own this data. Regional/dimensional analytics, referenced in passing in §4.1 below, are formalized in [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md). Neither status update changes this document's own workflow model.

**Status update ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)).** §5.2's Pocket Builder description is corrected: the engineer never nominates an "inside substation" or a "rest of grid" reference — only Circuit Terminal opening points. The evaluation result is now "Boundary Effective" (at least one isolated island formed) or "Boundary Ineffective," and may report more than one isolated island; §5.2 below reflects this terminology. The underlying evaluation mechanism this UX consumes is unchanged in kind (a live, stateless, synchronous call after every selection change) — only its input/output shape is corrected.

---

## 1. Purpose

The Engineering Workspace is the shared architectural concept — not a single reusable UI component, but a common shape every Defence Scheme module's own Draft-editing experience follows — for how an engineer designs a scheme version. It formalizes an iterative, non-linear workflow, replacing any notion of a fixed, step-by-step wizard.

## 2. Scope

A Draft Scheme Version (§2 of [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md)) is a **user-scoped Engineering Workspace** — see [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §5 for the precise meaning of "user-scoped" with respect to evaluation snapshot selection. This document covers the workflow and interaction shape; it does not itself define API contracts or UI component detail, which remain each scheme module's own frontend concern (CLAUDE.md §15, A12).

## 3. Capabilities

An Engineering Workspace supports, in any order, repeatedly, before Publication:

- creating a new Draft from zero;
- copying a previous version (§5 of [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md));
- selecting a Stage Setting Set (UFLS/UVLS only — [stage-setting-set-architecture.md](stage-setting-set-architecture.md));
- defining target MW per stage or priority group;
- browsing the candidate universe (§4, below);
- selecting Transformer Terminals for direct assignment;
- constructing Boundary Pockets ([boundary-pocket-architecture.md](boundary-pocket-architecture.md));
- assigning selected actions to a stage or priority group;
- removing and re-adding assignments;
- switching or comparing evaluation snapshots ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md) §5);
- continuously updating stage totals and findings, live, as the design changes;
- filtering and analytics over the candidate universe and the current assignment set, including Regional Engineering Analytics ([regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md)) — informational, never a validation rule;
- formal Publication review — the point at which structural prerequisites and finding-based publication treatment (§6 of [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)) are surfaced together, before the Publish action itself.

**The workflow is iterative, not a linear form wizard.** An engineer may build three stages, review findings, revisit the first stage's assignments, switch evaluation snapshots to compare, and only then proceed to Publication — no capability above is gated behind completing another in sequence, except where a genuine dependency exists (e.g. a Boundary Pocket cannot be assigned to a stage until its evaluation is Boundary Effective, per [boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7).

## 4. Candidate Universe and Assignment Universe

These are deliberately distinct concepts, never conflated:

- The **candidate universe** is every Transformer Terminal (or, for Boundary Pocket construction, every Circuit Terminal) an engineer could potentially select — resolved from Equipment Registry, enriched with read-only display metadata from every relevant registry, never filtered down to "only the ones GridDefence thinks are appropriate."
- The **assignment universe** is the specific set an engineer has actually assigned within the current Draft.

### 4.1 Candidate view metadata

Candidate views may expose, per candidate, resolved read-only at request time (never persisted into scheme data, per §6 of [shared-defence-scheme-domain-model.md](shared-defence-scheme-domain-model.md)):

- Substation, Region, State, GM Zone, Grid Owner (Substation Registry);
- Voltage, Transformer, Transformer Terminal, Circuit Terminal (Equipment Registry);
- current MW (via [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md)'s evaluation surface);
- ALSF capability;
- Sensitive Customer impact;
- lifecycle/resolution state (e.g. `ENTERED_IN_ERROR` correction status from the owning registry);
- already-assigned state (within the current Draft, and optionally across other currently-Published versions of the same or other schemes, for Rule-1-equivalent awareness during design);
- additional future metadata, without requiring a redesign of this view — see §4.2.

### 4.2 Extensible, service-driven filtering

**Candidate filtering must be extensible and service-driven, not a fragile static dropdown enumerating today's known metadata fields.** A new candidate metadata source (a future registry, a future finding type) must be addable to candidate filtering without redesigning the candidate view's own contract shape — the concrete mechanism (a generic filter-descriptor API, a metadata-registration pattern) is an implementation decision left to the module that first builds this view, constrained only by this requirement.

### 4.3 Non-removal on adverse metadata

Consistent with [scheme-engineering-principles.md](scheme-engineering-principles.md) §6:

- **Lack of ALSF capability must not remove a candidate automatically.** It remains selectable; selecting it produces a Critical finding, surfaced in the candidate view and carried into the assignment's own findings once selected.
- **Sensitive Customer association does not silently remove an existing assignment.** It remains assigned; the association produces a finding.

## 5. Assignment Interaction

### 5.1 Transformer Terminal (direct assignment)

- Checkbox selection over the candidate universe is the appropriate interaction shape.
- Selections accumulate into a basket/staged-selection area — not committed to the scheme immediately on checkbox click.
- An explicit "Assign to Stage" (or "Assign to Priority Group") action commits the staged selections into the current Draft's assignment universe.

### 5.2 Boundary Pocket

- The engineer enters a dedicated Pocket Builder interaction.
- Circuit Terminals are selected incrementally — never an "inside substation," a pocket name, or a "rest of grid" reference; those concepts do not exist in this workflow ([ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md)).
- The system evaluates boundary effectiveness after every change ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7), live, and reports every isolated island the current selection produces — zero, one, or many.
- The UX must visually distinguish three states: **Boundary Ineffective** (not yet assignable — this state exists only inside the Pocket Builder, never in Scheme Data), **Boundary Effective, not yet assigned** (at least one isolated island formed), and **assigned pocket** (effective and committed to a stage/priority group). When more than one isolated island is formed, the UX presents all of them, never only one.
- A Boundary Ineffective evaluation cannot be assigned — enforced at the service layer (the assignment-commit action rejects an evaluation that formed no isolated island), not only in the UI. There is no "assignable but flagged" state; a pocket becomes part of Scheme Data only once its evaluation is Boundary Effective ([boundary-pocket-architecture.md](boundary-pocket-architecture.md) §7).

### 5.3 Moving an assignment between stages

May be implemented as delete-and-add (removing the assignment from its current stage/priority group, re-adding it to another), provided:
- the UX presents this as a single, smooth "move" action to the engineer, never a two-step process they must manually reconcile;
- the resulting audit history remains understandable — a reviewer reading the audit log later should be able to recognize a move as a move, not be confused by an apparently unrelated delete followed by an apparently unrelated add. The exact audit-record shape that achieves this (a paired delete/add correlated by a shared operation id, or a first-class "moved" audit event type) is an implementation decision, constrained by this requirement, not resolved here.

## 6. Relationship to Findings and Publication

The Engineering Workspace surfaces findings continuously (§3, "continuously updating stage totals and findings") throughout Draft, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md). Formal Publication review (§3, final bullet) is where structural prerequisites and finding-based publication treatment are presented together as the basis for the Publish decision, per [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) — the Engineering Workspace does not itself decide whether Publication is permitted; it presents the evidence an Administrator uses to decide.

Concretely, this continuous-findings-plus-Publication-review surface is the [Engineering Review Panel](engineering-review-panel-architecture.md) — the panel is the Engineering Workspace's own review facet, distinct from its candidate-browsing and assignment-editing facets (§3–§5, above), sharing the same Draft/Published version context.

## 7. What the Engineering Workspace Does Not Do

- It never performs an authoritative engineering calculation itself (CLAUDE.md A12) — every MW figure, every finding, every completeness determination is backend-computed and presented, never computed client-side.
- It never automatically resolves a finding, removes a candidate, or redesigns a Boundary Pocket (§6 of [scheme-engineering-principles.md](scheme-engineering-principles.md)).
- It is not itself a new bounded context or module — it is a shared workflow shape each Defence Scheme module's own frontend implements against its own backend data, per CLAUDE.md §15.
