# GridDefence System Workflow

This document describes the complete engineering workflow GridDefence supports, from the initial engineering study through to the continuous validation of a published scheme. It expands [01-engineering-philosophy.md](01-engineering-philosophy.md) §5 and §7 into a single, end-to-end picture. It does not introduce any step, decision point, or system behaviour beyond what that document already establishes.

---

## 1. The Complete Workflow

```
              ┌─────────────────────┐
              │  Engineering Study  │   (external — PSS®E, engineering judgement)
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────────┐
              │ PSS/E Snapshot Selection│
              └──────────┬──────────────┘
                         ▼
              ┌─────────────────────┐
              │   Load Assessment   │
              └──────────┬──────────┘
                         ▼
              ┌──────────────────────────┐
              │ Sensitive Customer Review│
              └──────────┬───────────────┘
                         ▼
              ┌───────────────────────────────┐
              │ Relay Capability Verification │
              └──────────┬────────────────────┘
                         ▼
              ┌────────────────────────────┐
              │ Selection of Shedding      │
              │ Actions                    │
              └──────────┬─────────────────┘
                         ▼
              ┌─────────────────────┐
              │  Stage Coordination │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │       Review        │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │     Publication     │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────────┐
              │  Continuous Validation  │◄────┐
              └──────────┬──────────────┘     │
                         │                     │
                         │  finding raised,    │  no material
                         │  engineer decides   │  finding —
                         │  review is needed   │  scheme remains
                         ▼                     │  Published
              (back to Engineering Study /     │
               a new Working Draft) ───────────┘
```

The workflow is linear from Engineering Study through Publication — each step depends on the one before it, and a scheme cannot skip a step. After Publication, Continuous Validation runs indefinitely against the Published Scheme, and only ever *reports* — it never re-enters the workflow automatically. Re-entering the workflow (starting a new Working Draft) is always an engineer's own decision.

---

## 2. Purpose of Each Step

### Engineering Study

An external engineering study (outside GridDefence) determines the operational requirement a scheme must satisfy — for example, the total quantum of load that must be shed to arrest a given frequency excursion. GridDefence does not perform this study and does not calculate this figure; it is the starting input the rest of the workflow implements (01-engineering-philosophy.md §5, Step 1).

### PSS/E Snapshot Selection

The engineer selects a PSS®E load snapshot appropriate to the study being designed against — peak demand, off-peak demand, a seasonal condition, or a specific operational scenario. This snapshot becomes the operational reference for every subsequent step until a different one is selected (01-engineering-philosophy.md §5, Step 2). See **PSS/E Load Snapshot** in [02-engineering-concepts.md](02-engineering-concepts.md).

### Load Assessment

Using the selected snapshot, the engineer identifies which loads are actually available in the network to be shed, and how much each one represents — most commonly transformer bays, occasionally transmission lines (01-engineering-philosophy.md §5, Step 3).

### Sensitive Customer Review

Every candidate load identified in Load Assessment is checked against the Sensitive Customer registry. Any load serving a hospital, airport, strategic industry, or other protected connection is removed from consideration before the engineer proceeds further (01-engineering-philosophy.md §5, Step 4).

### Relay Capability Verification

For each remaining candidate, the engineer confirms — via the Relay Registry — that the bay or switching point is actually capable of being operated as a Grid Defence action. A load that cannot be answered "yes" here cannot be selected, regardless of how attractive it looks on paper (01-engineering-philosophy.md §5, Step 5).

### Selection of Shedding Actions

The engineer chooses which validated, capable, non-sensitive loads to actually include, and how — as direct Transformer Bay or Line Bay Shedding, or as a Boundary Line action isolating a Load Pocket. This is the step where individual engineering choices become concrete Shedding Actions (01-engineering-philosophy.md §5, Step 6).

### Stage Coordination

Selected Shedding Actions are grouped into Stages, each with its own triggering threshold and time delay. How actions are distributed across stages — which sheds first, which sheds later — is entirely an engineering judgement about how the disturbance is expected to progress (01-engineering-philosophy.md §5, Step 7).

### Review

The completed Working Draft undergoes formal Scheme Review: another engineer (or the same engineer, per whatever review policy applies) evaluates completeness, technical soundness, and currency against the latest known network condition before the scheme may proceed to publication (01-engineering-philosophy.md §5, Step 8).

### Publication

Once reviewed and approved, the scheme is published: it becomes the current operational reference, and its engineering metadata — version, review information, approval details, remarks, revision history — is permanently recorded. Any previously Published version of the same scheme type becomes an Archived Scheme at this moment (01-engineering-philosophy.md §5, Step 8).

### Continuous Validation

From the moment a scheme is published, and for as long as it remains published, every new PSS®E import is compared against it — checking whether the topology and loading the scheme was designed against still match reality. Findings (a removed transformer, a removed line, an invalidated bay assignment, a materially changed expected shed load) are reported to engineers. GridDefence never redesigns the scheme in response; the engineer decides whether the finding warrants opening a new Working Draft (01-engineering-philosophy.md §7). This is the one step in the workflow that does not "complete" — it runs for as long as the scheme is Published.

---

## 3. What This Workflow Deliberately Does Not Include

- **No automatic re-design.** A Continuous Validation finding never produces a new scheme version by itself — it only ever produces a finding for an engineer to act on (see [06-validation-philosophy.md](06-validation-philosophy.md)).
- **No automatic publication.** A Working Draft never becomes a Published Scheme without passing through Review — there is no "fast path" that skips it.
- **No merging of steps.** Sensitive Customer Review and Relay Capability Verification are deliberately separate steps, even though both filter candidate loads — they answer different engineering questions (policy exclusion vs. physical capability) and a finding from one must never be mistaken for a finding from the other.
