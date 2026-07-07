# GridDefence Validation Philosophy

This document establishes the philosophy governing how GridDefence validates existing Grid Defence Schemes against current network information. It does not define detailed validation rules, thresholds, or algorithms — those are engineering decisions to be made when a specific validation capability is designed, each grounded in this philosophy. This document exists so that whoever designs those future rules — engineer, developer, or AI coding agent — starts from the same, correct understanding of what validation is and is not.

---

## 1. The Core Distinction

GridDefence's entire approach to validation rests on one distinction, and every future validation capability must preserve it:

> **Engineering Validation** is GridDefence's job. **Engineering Decision** is the engineer's job.

|  | Engineering Validation | Engineering Decision |
|---|---|---|
| **What it is** | An automated comparison between an existing scheme and current network information, producing a finding | A deliberate, human, authenticated choice about how to respond to a finding |
| **Who performs it** | GridDefence, continuously, without being asked | An engineer, at a time of their choosing |
| **What it produces** | A report of impact — what changed, and what it affects | A change to engineering record — a new Working Draft, a registry correction, a resolved finding |
| **Can it be wrong?** | It can be imprecise or incomplete (an engineering judgement about what "significant" means may need refinement) — but it never has authority to be *overruled* automatically | It can be overturned only by another, later Engineering Decision |
| **Authority over the scheme** | None. A finding does not change the scheme. | Full. Only an Engineering Decision changes the scheme. |

Validation answers "what is different, and what does it affect." It never answers "what should we do about it." That second question belongs, exclusively, to the engineer.

---

## 2. Why This Distinction Exists

A Published Scheme's usefulness depends on it being both **stable** (an operator can rely on it without it silently changing) and **current** (it must remain technically executable against the real network). These two needs are in tension — the more often the system checks currency, the more tempting it becomes to let the system "fix" what it finds automatically, which would destroy stability.

GridDefence resolves the tension by keeping the two needs structurally separate: Validation protects currency by finding problems early and reporting them clearly. The Scheme Lifecycle protects stability by ensuring nothing changes the scheme except a deliberate Engineering Decision, taken through Scheme Review. Neither concern is allowed to compromise the other.

This is the same principle already stated in [01-engineering-philosophy.md](01-engineering-philosophy.md) §2: *"GridDefence detects engineering impacts. Engineers make engineering decisions."*

---

## 3. What Validation Detects

Validation continuously compares a scheme's assumptions against the latest available Operational Context. The kinds of impact it is responsible for detecting include:

### Removed transformer

A transformer bay referenced by a Shedding Action no longer exists in the current PSS/E Network Topology. The scheme's assumption that this bay is available to shed is no longer valid — the finding must make clear exactly which Shedding Action, in which Stage, in which Scheme, is affected.

### Removed transmission line

A line referenced directly by a Line Bay Shedding action, or forming part of a Boundary Line definition, no longer exists in the current topology. For a Boundary Line, this is a more serious finding than it might first appear: the *entire Load Pocket* the line helped isolate may no longer be correctly defined, not merely one action.

### Changed loading

The expected MW/MVAr contribution of a Shedding Action, evaluated against the latest PSS/E Load Snapshot, has changed materially from what informed the scheme's original design or its last review. This does not mean the action is invalid — loading legitimately varies — but a large enough change is engineering-significant and worth an engineer's attention.

### Missing relay capability

Equipment referenced by a Shedding Action no longer carries confirmed Grid Defence Capability in the Relay Registry — for example, a registry correction reclassified it, or new information revealed it was never actually capable. A scheme relying on this equipment can no longer assume it will execute as designed.

### Sensitive customer conflict

A load referenced by a Shedding Action has since become classified as a Sensitive Customer, or a Load Pocket now encloses a substation serving one. This is one of the highest-consequence findings validation can produce, since it touches operational policy directly, not only technical feasibility.

These five examples are illustrative, not exhaustive — this document does not attempt to enumerate every future validation check. Each shares the same shape: a fact the scheme depended on at design or review time no longer holds against current information.

---

## 4. What Validation Must Never Do

- **It must never modify a Published Scheme.** A finding is reported; the scheme is untouched until an engineer acts.
- **It must never silently resolve a finding.** Every finding remains visible and open until an engineer explicitly addresses it — there is no "auto-dismiss" for a finding that looks minor.
- **It must never assume silence means acceptance.** A finding that no engineer has reviewed is not the same as a finding an engineer has reviewed and judged immaterial — the two must never be conflated or displayed identically.
- **It must never block engineering activity by itself.** A finding is information; whether it warrants pausing operational reliance on a scheme is an engineering judgement, not a technical lock GridDefence imposes.
- **It must never invent a response on the engineer's behalf**, even a conservative one (e.g. automatically marking a Stage "inactive" because one action within it was flagged) — see [05-design-principles.md](05-design-principles.md), Principle 10.

---

## 5. The Engineer's Role When a Finding Is Raised

When Validation raises a finding, the engineer's decision is always one of:

1. **Acknowledge and defer** — the finding is understood, but does not currently warrant a scheme change (e.g. a loading change within an accepted tolerance the engineer judges immaterial).
2. **Open a new Working Draft** — the finding is significant enough to warrant Scheme Review, potentially resulting in a new Published Scheme.
3. **Correct Engineering Knowledge** — the finding actually reveals a registry error (for example, a genuine network change that should be reflected in the Equipment Registry or Relay Registry), which the engineer corrects directly, independent of any scheme change.

In every case, the decision — what was decided, by whom, when, and why — becomes part of the permanent engineering record (see **Engineering Metadata** and **Engineering Decision** in [02-engineering-concepts.md](02-engineering-concepts.md)), exactly as any other engineering decision does.

---

## 6. Relationship to Software Architecture

The software-level decisions that implement this philosophy for PSS/E-derived data specifically — why topology and load are separated, why an import never automatically alters approved data — are recorded in `docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md` and `docs/adr/ADR-010-engineering-decision-support-philosophy.md`. This document does not restate those decisions; it establishes the engineering reasoning that made them the correct decisions to make.
