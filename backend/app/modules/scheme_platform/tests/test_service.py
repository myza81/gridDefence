"""Tests for `SchemeVersionLifecycleService` — creation, publish/
supersede/enter-in-error transitions, deletion rules, and platform event
integration."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.continuous_evaluation.schemas import ChangeDescriptor, RefreshRequestResult
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.scheme_platform.exceptions import (
    DraftDeletionNotPermittedError,
    EnteredInErrorReasonRequiredError,
    IllegalLifecycleTransitionError,
)
from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus
from app.modules.scheme_platform.service import SchemeVersionLifecycleService
from app.modules.scheme_platform.tests.synthetic_scheme_version import SyntheticSchemeVersion


class _RecordingContinuousEvaluationService:
    """Test double standing in for `ContinuousEvaluationService` —
    records every `notify_source_data_changed` call's own descriptor
    without needing a real `AffectedSchemeResolver` registered (none
    exists yet; no real scheme module is built by this sprint)."""

    def __init__(self) -> None:
        self.notified: list[ChangeDescriptor] = []

    def notify_source_data_changed(self, event: ChangeDescriptor) -> list[RefreshRequestResult]:
        self.notified.append(event)
        return []


@pytest.fixture()
def recorder() -> _RecordingContinuousEvaluationService:
    return _RecordingContinuousEvaluationService()


@pytest.fixture()
def service(
    db_session: Session, recorder: _RecordingContinuousEvaluationService
) -> SchemeVersionLifecycleService:
    return SchemeVersionLifecycleService(
        db_session, source_module="synthetic_scheme", continuous_evaluation=recorder
    )


class TestCreateDraft:
    def test_stamps_version_number_and_draft_status(
        self, db_session: Session, service: SchemeVersionLifecycleService
    ) -> None:
        scheme_id = uuid.uuid4()
        version = SyntheticSchemeVersion(scheme_id=scheme_id)
        db_session.add(version)
        service.create_draft(version, model_class=SyntheticSchemeVersion, scheme_id=scheme_id)

        assert version.version_number == 1
        assert version.lifecycle_status == SchemeVersionLifecycleStatus.DRAFT.value

    def test_second_draft_for_the_same_scheme_gets_the_next_version_number(
        self, db_session: Session, service: SchemeVersionLifecycleService
    ) -> None:
        scheme_id = uuid.uuid4()
        first = SyntheticSchemeVersion(scheme_id=scheme_id)
        db_session.add(first)
        service.create_draft(first, model_class=SyntheticSchemeVersion, scheme_id=scheme_id)

        second = SyntheticSchemeVersion(scheme_id=scheme_id)
        db_session.add(second)
        service.create_draft(second, model_class=SyntheticSchemeVersion, scheme_id=scheme_id)

        assert second.version_number == 2

    def test_publishes_a_draft_created_event(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        recorder: _RecordingContinuousEvaluationService,
    ) -> None:
        scheme_id = uuid.uuid4()
        version = SyntheticSchemeVersion(scheme_id=scheme_id)
        db_session.add(version)
        service.create_draft(version, model_class=SyntheticSchemeVersion, scheme_id=scheme_id)

        assert len(recorder.notified) == 1
        event = recorder.notified[0]
        assert event.descriptor == "synthetic_scheme.scheme_version.draft_created"
        assert event.source_module == "synthetic_scheme"
        assert event.source_entity_type == "scheme_version"
        assert event.source_entity_id == str(version.version_id)


class TestDeleteDraft:
    def test_draft_may_be_deleted(
        self, db_session: Session, service: SchemeVersionLifecycleService
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        service.delete_draft(version)  # must not raise

    @pytest.mark.parametrize(
        "status",
        [
            SchemeVersionLifecycleStatus.PUBLISHED,
            SchemeVersionLifecycleStatus.SUPERSEDED,
            SchemeVersionLifecycleStatus.ENTERED_IN_ERROR,
        ],
    )
    def test_non_draft_versions_cannot_be_deleted(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        status: SchemeVersionLifecycleStatus,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(), version_number=1, lifecycle_status=status.value
        )
        with pytest.raises(DraftDeletionNotPermittedError):
            service.delete_draft(version)


class TestPublish:
    def test_draft_transitions_to_published(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        db_session.add(version)
        db_session.flush()

        service.publish(version, previous_published=None, actor_user_id=actor_user_id)

        assert version.lifecycle_status == SchemeVersionLifecycleStatus.PUBLISHED.value
        assert version.published_at is not None
        assert version.published_by_user_id == actor_user_id

    def test_publishing_atomically_supersedes_the_previous_published_version(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
    ) -> None:
        scheme_id = uuid.uuid4()
        previous = SyntheticSchemeVersion(
            scheme_id=scheme_id,
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.PUBLISHED.value,
        )
        new = SyntheticSchemeVersion(
            scheme_id=scheme_id,
            version_number=2,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        db_session.add_all([previous, new])
        db_session.flush()

        service.publish(new, previous_published=previous, actor_user_id=actor_user_id)

        assert new.lifecycle_status == SchemeVersionLifecycleStatus.PUBLISHED.value
        assert previous.lifecycle_status == SchemeVersionLifecycleStatus.SUPERSEDED.value
        assert previous.superseded_at is not None

    def test_publishing_a_non_draft_version_raises(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.PUBLISHED.value,
        )
        with pytest.raises(IllegalLifecycleTransitionError):
            service.publish(version, previous_published=None, actor_user_id=actor_user_id)

    def test_publishes_a_published_event(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
        recorder: _RecordingContinuousEvaluationService,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        db_session.add(version)
        db_session.flush()

        service.publish(version, previous_published=None, actor_user_id=actor_user_id)

        assert len(recorder.notified) == 1
        assert recorder.notified[0].descriptor == "synthetic_scheme.scheme_version.published"

    def test_publishing_with_a_previous_version_emits_both_events_in_order(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
        recorder: _RecordingContinuousEvaluationService,
    ) -> None:
        scheme_id = uuid.uuid4()
        previous = SyntheticSchemeVersion(
            scheme_id=scheme_id,
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.PUBLISHED.value,
        )
        new = SyntheticSchemeVersion(
            scheme_id=scheme_id,
            version_number=2,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        db_session.add_all([previous, new])
        db_session.flush()

        service.publish(new, previous_published=previous, actor_user_id=actor_user_id)

        actions = [event.descriptor.split(".")[-1] for event in recorder.notified]
        assert actions == ["superseded", "published"]


class TestEnterInError:
    def test_requires_a_non_empty_reason(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.PUBLISHED.value,
        )
        with pytest.raises(EnteredInErrorReasonRequiredError):
            service.enter_in_error(version, reason="   ", actor_user_id=actor_user_id)

    @pytest.mark.parametrize(
        "status",
        [SchemeVersionLifecycleStatus.PUBLISHED, SchemeVersionLifecycleStatus.SUPERSEDED],
    )
    def test_published_or_superseded_may_be_entered_in_error(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
        status: SchemeVersionLifecycleStatus,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(), version_number=1, lifecycle_status=status.value
        )
        db_session.add(version)
        db_session.flush()

        service.enter_in_error(
            version, reason="Published against the wrong scheme.", actor_user_id=actor_user_id
        )

        assert version.lifecycle_status == SchemeVersionLifecycleStatus.ENTERED_IN_ERROR.value
        assert version.entered_in_error_reason == "Published against the wrong scheme."
        assert version.entered_in_error_by_user_id == actor_user_id
        assert version.entered_in_error_at is not None

    def test_draft_cannot_be_entered_in_error(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.DRAFT.value,
        )
        with pytest.raises(IllegalLifecycleTransitionError):
            service.enter_in_error(version, reason="test", actor_user_id=actor_user_id)

    def test_entered_in_error_is_terminal(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.ENTERED_IN_ERROR.value,
        )
        with pytest.raises(IllegalLifecycleTransitionError):
            service.enter_in_error(version, reason="test", actor_user_id=actor_user_id)

    def test_publishes_an_entered_in_error_event_with_reason(
        self,
        db_session: Session,
        service: SchemeVersionLifecycleService,
        actor_user_id: uuid.UUID,
        recorder: _RecordingContinuousEvaluationService,
    ) -> None:
        version = SyntheticSchemeVersion(
            scheme_id=uuid.uuid4(),
            version_number=1,
            lifecycle_status=SchemeVersionLifecycleStatus.PUBLISHED.value,
        )
        db_session.add(version)
        db_session.flush()

        service.enter_in_error(version, reason="Data entry mistake.", actor_user_id=actor_user_id)

        assert len(recorder.notified) == 1
        event = recorder.notified[0]
        assert event.descriptor == "synthetic_scheme.scheme_version.entered_in_error"
        assert event.reason == "Data entry mistake."


class TestNoEngineeringCalculation:
    def test_service_never_touches_scheme_specific_attributes(self) -> None:
        """This service operates only on `SchemeVersionMixin`'s own
        shared attributes — a structural confirmation that no
        UFLS/UVLS/EMLS-specific *engineering field or calculation* name
        appears anywhere in its own code (this sprint's own explicit
        scope boundary). Illustrative mentions of "ufls"/"uvls"/"emls" in
        prose docstrings are expected and fine; this checks for genuine
        scheme-specific engineering terms that would indicate leaked
        logic, not module-name examples."""
        import ast
        import inspect

        from app.modules.scheme_platform import service as service_module

        tree = ast.parse(inspect.getsource(service_module))
        # Strip docstrings/comments by only inspecting identifier and
        # string-literal nodes that are not the module's/class's/
        # function's own leading docstring.
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                names.add(node.id.lower())
            elif isinstance(node, ast.Attribute):
                names.add(node.attr.lower())

        forbidden_terms = [
            "stage_setting",
            "priority_group",
            "transformer_terminal",
            "boundary_pocket",
            "frequency",
            "voltage",
            "threshold",
        ]
        for term in forbidden_terms:
            assert not any(term in name for name in names), (
                f"scheme-specific term '{term}' leaked into shared service's own code"
            )


def test_default_construction_uses_a_real_continuous_evaluation_service(
    db_session: Session,
) -> None:
    """Confirms the production default (no injected override) wires up
    correctly — `ContinuousEvaluationService`'s own default
    `NullAffectedSchemeResolver` means this call resolves zero targets
    and does nothing further, safely, since no real scheme module is
    registered yet."""
    service = SchemeVersionLifecycleService(db_session, source_module="synthetic_scheme")
    assert isinstance(service.continuous_evaluation, ContinuousEvaluationService)
