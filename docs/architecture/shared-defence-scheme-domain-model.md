# Shared Defence Scheme Domain Model

Governing standard: [`.claude/CLAUDE.md`](../../.claude/CLAUDE.md) v1.1 (A8 template, A6 layering). Part of the [Engineering Scheme Architecture Pack](scheme-engineering-principles.md).

Related documents: [scheme-engineering-principles.md](scheme-engineering-principles.md), [stage-setting-set-architecture.md](stage-setting-set-architecture.md), [boundary-pocket-architecture.md](boundary-pocket-architecture.md), [engineering-workspace-architecture.md](engineering-workspace-architecture.md), [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md), [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md), [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md), [ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md); supersedes, in part, [ufls-module.md](ufls-module.md) §7–§8, [uvls-module.md](uvls-module.md) §7–§8, [emls-module.md](emls-module.md) §7–§8 (each retains a status note, not a rewrite — §9, below).

This document states the domain model shared by every Defence Scheme module (UFLS, UVLS, EMLS today; SPS/RAS, Black Start, Islanding Strategy, Restoration Planning in the future). It is deliberately implementation-ready in shape and boundaries, but does not freeze low-level schemas beyond what is needed to express the shared concepts precisely.

**Status update (Shared Defence-Scheme Platform implementation).** §2 (Scheme Version), §4 (Lifecycle), and §8 (Service Interfaces, lifecycle portion only) are now implemented as reusable backend/frontend infrastructure — see [shared-scheme-platform-implementation.md](shared-scheme-platform-implementation.md) for exactly what was built (`backend/app/modules/scheme_platform/`, `frontend/src/components/scheme-platform/`) and how a future concrete scheme module composes with it. No concrete scheme module (UFLS/UVLS/EMLS) has been built against it yet; no scheme-specific structure (§2.2 Version Stage, §2.3 Priority Group, §3 Shedding Assignments) is implemented by this update.

---

## 1. Defence Scheme

A **Defence Scheme** represents one defence-scheme family: UFLS, UVLS, or EMLS today. It is the stable identity a sequence of Scheme Versions belongs to — rarely changes, exists so "only one Published version" is scoped correctly (e.g. if GridDefence ever needs more than one distinct UFLS scheme, such as a future separate regional scheme, without a discriminator-flag workaround, mirroring [`ufls-module.md`](ufls-module.md) §5's own original reasoning for `UflsScheme`, unaffected by this pack).

A future scheme type (SPS, RAS, etc.) introduces its own Defence Scheme identity and its own module — it never becomes a new "type" value on a shared, generic scheme table (§8 of [scheme-engineering-principles.md](scheme-engineering-principles.md); [`domain-model.md`](domain-model.md) §5's existing "each scheme module is an independent bounded context... do not share tables" principle, unaffected).

## 2. Scheme Version

A **Scheme Version** is the versioned aggregate root — one complete, coherent scheme design as of a point in time, belonging to exactly one Defence Scheme. It owns:

- **Stage structure**, through a reference to a Stage Setting Set, where applicable (UFLS, UVLS — see [stage-setting-set-architecture.md](stage-setting-set-architecture.md)). EMLS has no Stage Setting Set; its Version Stages (Priority Groups, §2.3 below) are owned directly by the version, since there is no reusable threshold/delay structure to separate out ([`emls-module.md`](emls-module.md) §7.2, unaffected by ADR-016).
- **Version-specific target MW per stage** (or per priority group) — each stage's target MW is an external-study input, engineer-entered, never derived. `Version Total Target MW = sum(Stage Target MW)`, nothing else — there is no `Version Target Percentage` and no automatic scaling; a snapshot change never alters any target MW, at any level. See [regional-engineering-analytics-architecture.md](regional-engineering-analytics-architecture.md) §3 for the full statement and why this MVP-inspired percentage idea was explicitly rejected.
- **Shedding assignments** — direct Transformer Terminal assignments and Boundary Pocket assignments (§3, below).
- **Lifecycle** — `Draft → Published → Superseded | Entered in Error`, per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md) (§4, below).
- **Engineering remarks.**
- **Publication governance** — the Publication record, findings present at Publication, treatments applied, acknowledgements, publisher, timestamp (see [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)).
- **Audit history** — its own append-only log, per CLAUDE.md A4, owned by the scheme module, never centralized.

### 2.1 What a Scheme Version does not own

Unchanged from the existing architecture series, restated for clarity: a Scheme Version never owns substation identity/metadata, equipment identity, network topology, ALSF capability, Sensitive Customer association, or connectivity/reachability computation. Every one of these is referenced by id and resolved live from its owning module ([Scheme Data Consumption Matrix](scheme-data-consumption-matrix.md)).

### 2.2 Version Stage (staged schemes — UFLS, UVLS)

For UFLS and UVLS, each Version Stage combines:
- one referenced setting from the version's chosen Stage Setting Set;
- a version-specific target MW;
- assigned shedding actions (direct assignments and/or Boundary Pocket assignments);
- derived current MW (never stored as the source of truth — always resolved live, per [continuous-evaluation-architecture.md](continuous-evaluation-architecture.md));
- current findings and analytics (derived, never stored as the source of truth).

**A Published staged version must be complete:** every stage in the selected Stage Setting Set must exist in the version; every stage must have a target MW; every stage must have at least one shedding action. This is a structural Publication prerequisite (per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)), never configurable away.

### 2.3 Priority Group (EMLS)

EMLS has no automatic trigger, no threshold, and no Stage Setting Set. Its `EmlsPriorityGroup` ([`emls-module.md`](emls-module.md) §7.2, unaffected by this pack) is owned directly by the Scheme Version, ranked by `priority_order`, optionally carrying human-facing `invocation_guidance`, and otherwise follows the same assignment/target-MW/findings shape as a Version Stage. See [emls-engineering-philosophy.md](emls-engineering-philosophy.md).

## 3. Shedding Assignments

Two kinds, owned by whichever Version Stage or Priority Group they belong to.

### 3.1 Direct Transformer Terminal Assignment

A direct load-shedding assignment references the authoritative Transformer Terminal identity from the Equipment Registry — `transformer_terminal_id`, never a copy of substation, transformer, or breaker attributes. The scheme stores the assignment identity, not a frozen MW value; current MW is always derived from the applicable evaluation snapshot ([continuous-evaluation-architecture.md](continuous-evaluation-architecture.md)).

- **A Transformer Terminal may appear only once within the same Scheme Version, across all stages/priority groups.** It may also appear in another scheme (UFLS and UVLS both assigning the same terminal, for instance), subject to Rule 1-equivalent cross-scheme findings ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md)) — this pack does not introduce a cross-scheme uniqueness constraint, only a finding.
- **Within a stage or priority group, assignment order does not matter.**
- This supersedes [`ufls-module.md`](ufls-module.md) §7.4's own "Open Question 1/2" free-text `equipment_reference` placeholder, which existed only because Equipment Registry did not yet exist when that document was written. Equipment Registry is now complete — a direct assignment references `transformer_terminal_id` directly, with no placeholder and no future migration required.

### 3.2 Boundary Pocket Assignment

See [boundary-pocket-architecture.md](boundary-pocket-architecture.md), [ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md), and [ADR-019](../adr/ADR-019-boundary-pocket-evaluation-by-connected-component-discovery.md) (which corrects only the evaluation mechanism, not what is stored here) for the full model. In summary: **Scheme Data** stores only the engineer-selected Circuit Terminal opening-point set, as engineering intent — never an "inside substation," a pocket name, or a "rest of grid" reference (none exist as concepts, per ADR-019) — this is the assignment's own identity, immutable once Published, exactly like any other assignment. The derived isolated-island substation set(s) and `topology_version_id` in effect at the moment of Publication are **not** stored on the assignment itself — they are captured as Publication Evidence, within that Publication's own `PublicationRecord` ([findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) §2), since a `PublicationRecord` is immutable audit evidence, not Scheme Data (see [scheme-engineering-principles.md](scheme-engineering-principles.md) §11 for the full Scheme Data / Publication Record distinction). Current pocket composition and current MW are always derived, live, from the selected opening points against the applicable evaluation snapshot — never stored as the ongoing source of truth, and never stored anywhere within Scheme Data.

## 4. Scheme Version Lifecycle

Per [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md):

```text
Draft → Published → Superseded
Draft → Published → Entered in Error
                     Superseded → Entered in Error
```

- Drafts may be deleted.
- Published versions are immutable except for the permitted lifecycle actions (Entered in Error, with mandatory reason) and governance records (findings/acknowledgements accumulate against a Published version without changing its own assignment data).
- Publishing a new version atomically supersedes the currently Published version for that scheme.
- Only one Published version may exist per scheme at a time.
- Superseded versions remain historically readable.
- Published and Superseded versions may later be marked Entered in Error, with mandatory reason and audit.
- Entered in Error is terminal.

## 5. Version Copying

Copying a previous version copies:
- the referenced Stage Setting Set (UFLS/UVLS) or the priority-group structure (EMLS);
- stage/priority-group structure;
- Transformer Terminal assignments;
- Boundary Pocket assignments (the selected opening-point sets — not the captured baseline, which lives in the source version's `PublicationRecord`, never on the assignment itself, and is therefore never copyable in the first place);
- assignment-to-stage/priority-group arrangement.

Copying does **not** copy:
- target MW values;
- Publication status;
- Publication acknowledgements;
- review decisions;
- historical findings;
- calculated (derived) MW;
- audit actors or timestamps.

A copied version always starts as Draft, regardless of the source version's lifecycle state.

## 6. Analytics and Current Evaluation Boundary

The scheme owns: assignments, Stage Setting Set reference (where applicable), target MW, version metadata, lifecycle, remarks, Publication governance.

The scheme does not own or duplicate: current MW, Region, State, GM Zone, Grid Owner, ALSF state, Sensitive Customer state, topology, pocket composition, or operational snapshot data. These are resolved from authoritative sources at evaluation time ([Scheme Data Consumption Matrix](scheme-data-consumption-matrix.md)).

Reports and dashboards show the current operational interpretation unless a future, explicit historical-reporting mode is introduced. Changing a substation's Region, State, GM Zone, or other metadata changes current analytics and reports; it never rewrites the engineering assignment itself, which continues to reference the substation (via its Transformer Terminal or Boundary Pocket opening points) by stable id.

## 7. Cross-Cutting Business Rules (version-internal, owned by each scheme module)

Carried forward, unchanged in substance, from [`ufls-module.md`](ufls-module.md) §9 rules 7–8 (the "Rule 3"/"Rule 4" equivalents already resolved as version-internal, self-contained rules requiring no cross-module coupling):

1. A Transformer Terminal may not simultaneously be a direct assignment and appear within a Boundary Pocket's derived substation set, within the same Scheme Version — always enforced, never configurable.
2. A substation whose Substation Registry `grid_owner` classification is an excluded ownership classification (e.g. Independent Power Producer, Large Scale Solar) may not be assigned via any direct or Boundary Pocket assignment — always enforced, resolved via read-only lookup against Substation Registry.
3. Each scheme module's own tables contain no foreign key into another scheme module's schema — cross-scheme concerns are resolved exclusively through service-interface calls (CLAUDE.md A1), never direct table coupling.

## 8. Service Interfaces (shared shape)

Every Defence Scheme module exposes, at minimum:
- A read-only query interface for the current Published version and its structure.
- A read-only interface for a substation's or Transformer Terminal's assignment history across versions.
- `getProtectedAssignments(scope)` — unchanged in contract shape from [`ufls-module.md`](ufls-module.md) §13, now consumed by the Continuous Evaluation Engine's cross-scheme finding detection rather than by a dedicated Cross-Scheme Compliance module's own gating call (see [findings-and-publication-governance-architecture.md](findings-and-publication-governance-architecture.md) for how Rule 1/2-equivalent findings are now produced).

Every Defence Scheme module consumes, from other modules' service layers — never their repositories directly (CLAUDE.md A1): Substation Registry and Equipment Registry (assignment validity, read-enrichment), the Automatic Load Shedding Functionality Registry (capability findings), the Sensitive Customer Registry (association findings), Operational Snapshot/PSS/E Integration and the Boundary Pocket capability (recommendations, never a live dependency of Published data), and Core Platform/IAM (authorization, audit attribution).

## 9. Relationship to the Pre-Existing Module Documents

[`ufls-module.md`](ufls-module.md), [`uvls-module.md`](uvls-module.md), and [`emls-module.md`](emls-module.md) remain the authoritative source for: module ownership (§3–§4 of each), the full referenced-entity list (§6), the shared-vs-different comparison tables ([`uvls-module.md`](uvls-module.md) §7.1, [`emls-module.md`](emls-module.md) §7.1), validation rules not superseded here (§10 of each), security considerations (§15 of each), and testing priorities (§16 of each). Each document's §7 (assignment model, MW treatment) and §8 (lifecycle) are superseded by this document and [ADR-015](../adr/ADR-015-defence-scheme-version-lifecycle-simplification.md)/[ADR-016](../adr/ADR-016-stage-setting-set-as-reusable-versioned-entity.md)/[ADR-017](../adr/ADR-017-boundary-pocket-assignment-architecture.md) respectively — a short status note is added to each, pointing here, without rewriting the original text (CLAUDE.md §5.2).
