"""The shared Defence Scheme Version lifecycle (ADR-015; EDR-009;
docs/architecture/shared-defence-scheme-domain-model.md §4).

**This is the ratified, authoritative lifecycle — not CLAUDE.md A3's
general-purpose six-state Canonical Version Lifecycle.** Six Project
Owner engineering-discovery workshops (EDR-009) concluded a Defence
Scheme Version's lifecycle has exactly four states:

    Draft -> Published -> Superseded
                        -> Entered in Error
             Superseded -> Entered in Error

There is no `Under Review` state and no `Approved` state distinct from
`Published` — review and approval are evidence-gathering activity that
happens *within* Draft (made rigorous by continuously-visible findings,
per the Continuous Evaluation architecture), not separate gated states.
There is no `Archived` state — `Superseded` and `Entered in Error` are
both already permanent, queryable, terminal states.

`Superseded -> Published` reactivation is an explicitly open question
(ADR-015 §"Reactivation"; scheme-roadmap-corrections.md) — deliberately
**not** implemented here. The lifecycle this module enforces is
forward-only, exactly the four transitions ADR-015 names, no more.
"""

from __future__ import annotations

import enum

from app.modules.scheme_platform.exceptions import IllegalLifecycleTransitionError


class SchemeVersionLifecycleStatus(enum.StrEnum):
    """Exactly the four states ADR-015/EDR-009 name — no `UNDER_REVIEW`,
    no `APPROVED`, no `ARCHIVED`. Never reordered or renamed once shipped,
    since every future scheme module's own table stores these exact
    values (CLAUDE.md §11.3's own reference-data-over-enum guidance does
    not apply here: this is a closed, ratified engineering lifecycle, not
    an open reference list a future module might extend)."""

    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    ENTERED_IN_ERROR = "ENTERED_IN_ERROR"


# The exact, closed transition allow-list ADR-015 names — a plain set of
# (from, to) pairs, not a generic graph/state-machine framework (CLAUDE.md
# §21: no machinery beyond what four transitions actually need).
_Status = SchemeVersionLifecycleStatus
_LEGAL_TRANSITIONS: frozenset[tuple[_Status, _Status]] = frozenset(
    {
        (_Status.DRAFT, _Status.PUBLISHED),
        (_Status.PUBLISHED, _Status.SUPERSEDED),
        (_Status.PUBLISHED, _Status.ENTERED_IN_ERROR),
        (_Status.SUPERSEDED, _Status.ENTERED_IN_ERROR),
    }
)


def validate_transition(
    current: SchemeVersionLifecycleStatus, target: SchemeVersionLifecycleStatus
) -> None:
    """Raises `IllegalLifecycleTransitionError` unless `(current, target)`
    is one of ADR-015's own four named transitions. No reverse transition,
    no skip transition, no `Superseded -> Published` reactivation (an
    explicitly open question this module does not resolve)."""
    if (current, target) not in _LEGAL_TRANSITIONS:
        raise IllegalLifecycleTransitionError(current, target)
