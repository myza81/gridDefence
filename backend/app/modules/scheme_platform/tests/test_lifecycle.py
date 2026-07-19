"""Tests for the shared lifecycle transition allow-list (ADR-015)."""

from __future__ import annotations

import itertools

import pytest

from app.modules.scheme_platform.exceptions import IllegalLifecycleTransitionError
from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus, validate_transition

_Status = SchemeVersionLifecycleStatus

_LEGAL = [
    (_Status.DRAFT, _Status.PUBLISHED),
    (_Status.PUBLISHED, _Status.SUPERSEDED),
    (_Status.PUBLISHED, _Status.ENTERED_IN_ERROR),
    (_Status.SUPERSEDED, _Status.ENTERED_IN_ERROR),
]


class TestExactlyFourStates:
    def test_no_under_review_or_approved_or_archived_state_exists(self) -> None:
        assert {s.value for s in SchemeVersionLifecycleStatus} == {
            "DRAFT",
            "PUBLISHED",
            "SUPERSEDED",
            "ENTERED_IN_ERROR",
        }


class TestLegalTransitions:
    @pytest.mark.parametrize("current,target", _LEGAL)
    def test_each_adr015_transition_is_legal(
        self, current: SchemeVersionLifecycleStatus, target: SchemeVersionLifecycleStatus
    ) -> None:
        validate_transition(current, target)  # must not raise


class TestIllegalTransitions:
    @pytest.mark.parametrize(
        "current,target",
        [pair for pair in itertools.product(_Status, _Status) if pair not in _LEGAL],
    )
    def test_every_other_pair_is_illegal(
        self, current: SchemeVersionLifecycleStatus, target: SchemeVersionLifecycleStatus
    ) -> None:
        with pytest.raises(IllegalLifecycleTransitionError):
            validate_transition(current, target)

    def test_no_under_review_state_is_reachable(self) -> None:
        # There is no `UNDER_REVIEW` value to even attempt — this test
        # documents the absence explicitly (this sprint's own
        # instructions: preserve ADR-015's four-state model exactly).
        assert not hasattr(SchemeVersionLifecycleStatus, "UNDER_REVIEW")
        assert not hasattr(SchemeVersionLifecycleStatus, "APPROVED")
        assert not hasattr(SchemeVersionLifecycleStatus, "ARCHIVED")

    def test_superseded_to_published_reactivation_is_not_implemented(self) -> None:
        """ADR-015's own "Reactivation" section: `Superseded -> Published`
        is an explicitly open question, deliberately not resolved here."""
        with pytest.raises(IllegalLifecycleTransitionError):
            validate_transition(_Status.SUPERSEDED, _Status.PUBLISHED)

    def test_no_reverse_transition(self) -> None:
        with pytest.raises(IllegalLifecycleTransitionError):
            validate_transition(_Status.PUBLISHED, _Status.DRAFT)

    def test_entered_in_error_is_terminal(self) -> None:
        for target in _Status:
            with pytest.raises(IllegalLifecycleTransitionError):
                validate_transition(_Status.ENTERED_IN_ERROR, target)
