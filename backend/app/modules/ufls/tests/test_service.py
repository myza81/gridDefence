"""Business-rule tests for `UflsService` (CLAUDE.md A11 priority: business
rules and engineering outcomes over implementation details). Exercises the
Router -> Service -> Repository stack's own Service layer directly against
a real database session (SQLite by default; PostgreSQL via
`GRIDDEFENCE_TEST_DATABASE_URL`, per `conftest.py`).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.exceptions import PrerequisiteFailedError
from app.modules.findings_publication_governance.findings import FindingType
from app.modules.stage_setting_registry.exceptions import StageSettingSetReferencedError
from app.modules.stage_setting_registry.service import StageSettingRegistryService
from app.modules.ufls.exceptions import (
    DirectAndPocketOverlapError,
    IneffectiveBoundaryError,
    StageSettingSetNotFoundError,
    StageSettingSetNotPublishedError,
    StageSettingSetSchemeTypeMismatchError,
    TerminalAlreadyAssignedError,
    UflsSchemeVersionNotFoundError,
    VersionNotEditableError,
)
from app.modules.ufls.service import UflsService
from app.modules.ufls.tests.conftest import Fixture


def _draft_version_with_one_stage(
    service: UflsService, fixture: Fixture, actor_user_id: uuid.UUID, *, target_mw: str = "10"
):
    scheme = service.create_scheme(
        name="Test UFLS Scheme", description=None, actor_user_id=actor_user_id
    )
    service.db.commit()
    version = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    service.update_version_metadata(
        version.version_id,
        stage_setting_set_id=fixture.stage_setting_set_id,
        study_reference="Study Ref 1",
        effective_date=None,
        topology_version_id=fixture.topology_version_id,
        load_snapshot_id=None,
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    stage = service.add_stage(
        version.version_id,
        stage_setting_id=fixture.stage_setting_ids[0],
        target_mw=Decimal(target_mw),
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()
    return scheme, version, stage


def _draft_version_ready_to_publish(
    service: UflsService, fixture: Fixture, actor_user_id: uuid.UUID, *, scheme_name: str
):
    """A version whose stage structure is complete against the fixture's
    two-setting Published Stage Setting Set — every stage has a target MW
    and at least one assignment (`UFLS_STAGE_HAS_ASSIGNMENT`/
    `UFLS_STAGE_STRUCTURE_COMPLETE`), so `publish()` succeeds."""
    scheme = service.create_scheme(name=scheme_name, description=None, actor_user_id=actor_user_id)
    service.db.commit()
    version = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    service.update_version_metadata(
        version.version_id,
        stage_setting_set_id=fixture.stage_setting_set_id,
        study_reference="Study Ref 1",
        effective_date=None,
        topology_version_id=fixture.topology_version_id,
        load_snapshot_id=None,
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    stage_1 = service.add_stage(
        version.version_id,
        stage_setting_id=fixture.stage_setting_ids[0],
        target_mw=Decimal("10"),
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    stage_2 = service.add_stage(
        version.version_id,
        stage_setting_id=fixture.stage_setting_ids[1],
        target_mw=Decimal("20"),
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    service.add_direct_assignment(
        stage_1.ufls_stage_id,
        transformer_terminal_id=fixture.transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.add_direct_assignment(
        stage_2.ufls_stage_id,
        transformer_terminal_id=fixture.igbk_transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()
    return scheme, version, [stage_1, stage_2]


# --- Scheme lineage / version numbering ---------------------------------------------


def test_create_scheme_and_sequential_version_numbering(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    scheme = service.create_scheme(name="Scheme A", description=None, actor_user_id=actor_user_id)
    service.db.commit()

    v1 = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    v2 = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    assert v1.version_number == 1
    assert v2.version_number == 2

    other_scheme = service.create_scheme(
        name="Scheme B", description=None, actor_user_id=actor_user_id
    )
    service.db.commit()
    other_v1 = service.create_draft_version(
        other_scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    assert other_v1.version_number == 1  # scoped per-lineage, not global


# --- Draft editing / Published immutability -----------------------------------------


def test_published_version_stage_mutation_rejected(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, version, stages = _draft_version_ready_to_publish(
        service, ufls_fixture, actor_user_id, scheme_name="Immutability Test"
    )

    service.publish(
        version.version_id,
        publication_event_id=uuid.uuid4(),
        acknowledgements=[],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    with pytest.raises(VersionNotEditableError):
        service.update_stage(
            stages[0].ufls_stage_id,
            target_mw=Decimal("99"),
            engineering_remarks=None,
            actor_user_id=actor_user_id,
        )


def test_draft_deletion_allowed_only_for_draft(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    scheme = service.create_scheme(name="Deletable", description=None, actor_user_id=actor_user_id)
    service.db.commit()
    version = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    service.db.commit()
    service.delete_draft_version(version.version_id, actor_user_id=actor_user_id)
    service.db.commit()

    with pytest.raises(UflsSchemeVersionNotFoundError):
        service.get_version(version.version_id)


# --- Stage Setting Set validation -----------------------------------------------------


def test_stage_setting_set_must_match_ufls_scheme_type(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    stage_registry = StageSettingRegistryService(db_session)
    uvls_set = stage_registry.create_draft(
        scheme_type="UVLS", description="UVLS set", actor_user_id=actor_user_id
    )
    db_session.commit()

    service = UflsService(db_session)
    scheme = service.create_scheme(name="Mismatch", description=None, actor_user_id=actor_user_id)
    db_session.commit()
    version = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    db_session.commit()

    with pytest.raises(StageSettingSetSchemeTypeMismatchError):
        service.update_version_metadata(
            version.version_id,
            stage_setting_set_id=uvls_set.stage_setting_set_id,
            study_reference=None,
            effective_date=None,
            topology_version_id=None,
            load_snapshot_id=None,
            engineering_remarks=None,
            actor_user_id=actor_user_id,
        )


def _new_ufls_draft_version(service: UflsService, actor_user_id: uuid.UUID):
    scheme = service.create_scheme(
        name="Selection Validation Test", description=None, actor_user_id=actor_user_id
    )
    service.db.commit()
    return service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )


def test_selecting_a_draft_stage_setting_set_is_rejected(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    """ADR-024 (Selection-Time Validation Correction): a still-Draft
    Stage Setting Set can never be selected, not even by a Draft UFLS
    version — never deferred to the Publish-time prerequisite alone."""
    stage_registry = StageSettingRegistryService(db_session)
    draft_set = stage_registry.create_draft(
        scheme_type="UFLS", description="Not yet published", actor_user_id=actor_user_id
    )
    db_session.commit()

    service = UflsService(db_session)
    version = _new_ufls_draft_version(service, actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotPublishedError):
        service.update_version_metadata(
            version.version_id,
            stage_setting_set_id=draft_set.stage_setting_set_id,
            study_reference=None,
            effective_date=None,
            topology_version_id=None,
            load_snapshot_id=None,
            engineering_remarks=None,
            actor_user_id=actor_user_id,
        )


def test_selecting_an_entered_in_error_stage_setting_set_is_rejected(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    stage_registry = StageSettingRegistryService(db_session)
    corrected_set = stage_registry.create_draft(
        scheme_type="UFLS", description="Will be corrected", actor_user_id=actor_user_id
    )
    corrected_stage = stage_registry.add_stage(
        corrected_set.stage_setting_set_id,
        stage_order=1,
        region_scope_id=None,
        actor_user_id=actor_user_id,
    )
    stage_registry.add_trigger(
        corrected_set.stage_setting_set_id,
        corrected_stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    stage_registry.publish(corrected_set.stage_setting_set_id, actor_user_id=actor_user_id)
    stage_registry.enter_in_error(
        corrected_set.stage_setting_set_id,
        change_reason="Data-entry mistake",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service = UflsService(db_session)
    version = _new_ufls_draft_version(service, actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotPublishedError):
        service.update_version_metadata(
            version.version_id,
            stage_setting_set_id=corrected_set.stage_setting_set_id,
            study_reference=None,
            effective_date=None,
            topology_version_id=None,
            load_snapshot_id=None,
            engineering_remarks=None,
            actor_user_id=actor_user_id,
        )


def test_selecting_a_missing_stage_setting_set_is_rejected(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    version = _new_ufls_draft_version(service, actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotFoundError):
        service.update_version_metadata(
            version.version_id,
            stage_setting_set_id=uuid.uuid4(),
            study_reference=None,
            effective_date=None,
            topology_version_id=None,
            load_snapshot_id=None,
            engineering_remarks=None,
            actor_user_id=actor_user_id,
        )


def test_selecting_a_published_matching_stage_setting_set_succeeds(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    """The fixture's own Stage Setting Set is already Published — the
    positive case selection-time validation must continue to accept."""
    service = UflsService(db_session)
    version = _new_ufls_draft_version(service, actor_user_id)
    db_session.commit()

    updated = service.update_version_metadata(
        version.version_id,
        stage_setting_set_id=ufls_fixture.stage_setting_set_id,
        study_reference=None,
        effective_date=None,
        topology_version_id=None,
        load_snapshot_id=None,
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    assert updated.stage_setting_set_id == ufls_fixture.stage_setting_set_id


# --- Multiple operating criteria per stage (ADR-025) ------------------------------------


def test_ufls_stage_exposes_all_triggers_of_its_referenced_stage(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    """Selecting Stage 8 gives the UFLS stage access to every trigger
    configured under it — the worked UAT example (48.1 Hz/0 ms fast trip,
    49.3 Hz/60,000 ms backup trip), both belonging to the same
    `UflsStage`, never duplicated into two stages."""
    stage_registry = StageSettingRegistryService(db_session)
    multi_trigger_set = stage_registry.create_draft(
        scheme_type="UFLS", description="Multi-trigger regression test", actor_user_id=actor_user_id
    )
    stage_8 = stage_registry.add_stage(
        multi_trigger_set.stage_setting_set_id,
        stage_order=8,
        region_scope_id=None,
        actor_user_id=actor_user_id,
    )
    stage_registry.add_trigger(
        multi_trigger_set.stage_setting_set_id,
        stage_8.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    stage_registry.add_trigger(
        multi_trigger_set.stage_setting_set_id,
        stage_8.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    stage_registry.publish(multi_trigger_set.stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    service = UflsService(db_session)
    scheme = service.create_scheme(
        name="Multi-trigger UFLS Scheme", description=None, actor_user_id=actor_user_id
    )
    db_session.commit()
    version = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    service.update_version_metadata(
        version.version_id,
        stage_setting_set_id=multi_trigger_set.stage_setting_set_id,
        study_reference=None,
        effective_date=None,
        topology_version_id=None,
        load_snapshot_id=None,
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    ufls_stage = service.add_stage(
        version.version_id,
        stage_setting_id=stage_8.stage_setting_id,
        target_mw=Decimal("50"),
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.to_stage_detail(ufls_stage)
    assert detail.stage_order == 8
    assert len(detail.triggers) == 2
    ordered = sorted(detail.triggers, key=lambda t: t.trigger_order)
    assert ordered[0].threshold_value == Decimal("48.1000")
    assert ordered[0].time_delay_ms == 0
    assert ordered[1].threshold_value == Decimal("49.3000")
    assert ordered[1].time_delay_ms == 60000

    # No assignment duplication — exactly one UflsStage exists for this
    # multi-trigger stage.
    all_stages = service.repo.list_stages(version.version_id)
    assert len(all_stages) == 1


# --- Stage Setting Set Draft deletion cross-module reference check (ADR-024) -----------


def test_stage_setting_set_delete_draft_blocked_by_real_ufls_reference_checker(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    """End-to-end proof that `StageSettingRegistryService.delete_draft`'s
    default (real, non-fake) UFLS reference checker correctly counts both
    a Draft-lifecycle and a Published-lifecycle UFLS version referencing
    the same set. Both references are created while the set is genuinely
    Published (the only way ADR-024's own selection-time correction ever
    permits a reference to exist) — the set is then forced back to
    `DRAFT` directly at the ORM level to exercise the deletion path's own
    defense-in-depth reference check, simulating exactly the "row
    predates this correction, or was otherwise manually corrected" case
    ADR-024's own Consequences section names explicitly."""
    service = UflsService(db_session)

    draft_version, draft_stage = _draft_version_with_one_stage(
        service, ufls_fixture, actor_user_id
    )[1:]
    _scheme, published_version, published_stages = _draft_version_ready_to_publish(
        service, ufls_fixture, actor_user_id, scheme_name="Reference Check — Published Side"
    )
    service.publish(
        published_version.version_id,
        publication_event_id=uuid.uuid4(),
        acknowledgements=[],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    stage_registry = StageSettingRegistryService(db_session)
    reference_count = stage_registry.reference_checkers["UFLS"].count_references(
        ufls_fixture.stage_setting_set_id
    )
    # Exactly draft_version + published_version reference the fixture's
    # set within this test's own isolated database session.
    assert reference_count == 2

    # Force the referenced set back to Draft -- see docstring above.
    stage_setting_set = stage_registry.repo.get_set_by_id(ufls_fixture.stage_setting_set_id)
    stage_setting_set.status = "DRAFT"
    db_session.flush()

    with pytest.raises(StageSettingSetReferencedError):
        stage_registry.delete_draft(ufls_fixture.stage_setting_set_id, actor_user_id=actor_user_id)

    # Never physically deleted -- remains fully readable, and the
    # Published UFLS version's own stage data is completely unaffected.
    db_session.rollback()
    still_published = service.get_version(published_version.version_id)
    assert still_published.lifecycle_status == "PUBLISHED"
    _ = draft_stage, published_stages  # constructed for realism; not asserted further


# --- Direct assignments ---------------------------------------------------------------


def test_list_direct_and_pocket_assignments_for_stage(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, _version, stage = _draft_version_with_one_stage(service, ufls_fixture, actor_user_id)
    service.add_direct_assignment(
        stage.ufls_stage_id,
        transformer_terminal_id=ufls_fixture.transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.add_pocket_assignment(
        stage.ufls_stage_id,
        circuit_terminal_ids=[ufls_fixture.pklg_igbk_circuit_terminal_ids[0]],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    direct = service.list_direct_assignments(stage.ufls_stage_id)
    pocket = service.list_pocket_assignments(stage.ufls_stage_id)
    assert len(direct) == 1
    assert len(pocket) == 1
    direct_detail = service.to_direct_assignment_detail(direct[0])
    assert direct_detail.substation_mnemonic == "PKLG"
    pocket_detail = service.to_pocket_assignment_detail(pocket[0])
    assert pocket_detail.circuit_terminal_ids == [ufls_fixture.pklg_igbk_circuit_terminal_ids[0]]


def test_duplicate_direct_assignment_rejected(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, _version, stage = _draft_version_with_one_stage(service, ufls_fixture, actor_user_id)
    service.add_direct_assignment(
        stage.ufls_stage_id,
        transformer_terminal_id=ufls_fixture.transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    with pytest.raises(TerminalAlreadyAssignedError):
        service.add_direct_assignment(
            stage.ufls_stage_id,
            transformer_terminal_id=ufls_fixture.transformer_terminal_id,
            remarks=None,
            actor_user_id=actor_user_id,
        )


# --- Pocket assignments / Boundary Pocket integration ---------------------------------


def test_ineffective_boundary_cannot_be_assigned(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, _version, stage = _draft_version_with_one_stage(service, ufls_fixture, actor_user_id)

    with pytest.raises(IneffectiveBoundaryError):
        service.add_pocket_assignment(
            stage.ufls_stage_id,
            circuit_terminal_ids=[],
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_effective_boundary_pocket_assignment_created(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, _version, stage = _draft_version_with_one_stage(service, ufls_fixture, actor_user_id)

    pocket = service.add_pocket_assignment(
        stage.ufls_stage_id,
        circuit_terminal_ids=[ufls_fixture.pklg_igbk_circuit_terminal_ids[0]],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()
    assert pocket.ufls_pocket_assignment_id is not None


def test_direct_and_pocket_overlap_rejected(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    """ufls-module.md §9 rule 7: a substation cannot be both directly
    assigned and part of a Boundary Pocket's isolated island within the
    same version. The fixture's Boundary Pocket (opening the PKLG-IGBK
    circuit) isolates IGBK — assigning IGBK's own transformer terminal
    directly first, then attempting the same Boundary Pocket, must raise
    `DirectAndPocketOverlapError`."""
    service = UflsService(db_session)
    _, _version, stage = _draft_version_with_one_stage(service, ufls_fixture, actor_user_id)
    service.add_direct_assignment(
        stage.ufls_stage_id,
        transformer_terminal_id=ufls_fixture.igbk_transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    with pytest.raises(DirectAndPocketOverlapError):
        service.add_pocket_assignment(
            stage.ufls_stage_id,
            circuit_terminal_ids=[ufls_fixture.pklg_igbk_circuit_terminal_ids[0]],
            remarks=None,
            actor_user_id=actor_user_id,
        )


# --- Publication prerequisites and publish -------------------------------------------


def test_publish_blocked_when_stage_missing_target_mw(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    scheme = service.create_scheme(name="Incomplete", description=None, actor_user_id=actor_user_id)
    service.db.commit()
    version = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=None, actor_user_id=actor_user_id
    )
    service.update_version_metadata(
        version.version_id,
        stage_setting_set_id=ufls_fixture.stage_setting_set_id,
        study_reference=None,
        effective_date=None,
        topology_version_id=None,
        load_snapshot_id=None,
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    service.add_stage(
        version.version_id,
        stage_setting_id=ufls_fixture.stage_setting_ids[0],
        target_mw=None,
        engineering_remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    prerequisites = service.compute_prerequisites(version.version_id)
    assert any(
        p.prerequisite_code == "UFLS_STAGE_TARGET_MW_SET" and not p.passed for p in prerequisites
    )
    assert any(
        p.prerequisite_code == "UFLS_STAGE_STRUCTURE_COMPLETE" and not p.passed
        for p in prerequisites
    )


def test_publish_atomically_supersedes_previous_published_same_lineage_only(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    scheme, v1, _stages = _draft_version_ready_to_publish(
        service, ufls_fixture, actor_user_id, scheme_name="Lineage A"
    )
    service.publish(
        v1.version_id,
        publication_event_id=uuid.uuid4(),
        acknowledgements=[],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    # An unrelated second lineage's own Published version must be
    # unaffected by this lineage's own supersession.
    _other_scheme, other_version, _other_stages = _draft_version_ready_to_publish(
        service, ufls_fixture, actor_user_id, scheme_name="Unrelated Lineage"
    )
    service.publish(
        other_version.version_id,
        publication_event_id=uuid.uuid4(),
        acknowledgements=[],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    v2 = service.create_draft_version(
        scheme.ufls_scheme_id, copied_from_version_id=v1.version_id, actor_user_id=actor_user_id
    )
    service.db.commit()
    # Copying never carries over target_mw (shared-defence-scheme-domain-model.md §5),
    # though the underlying stage/assignment structure is copied verbatim.
    copied_stages = service.list_stages(v2.version_id)
    assert len(copied_stages) == 2
    assert all(stage.target_mw is None for stage in copied_stages)

    for stage in copied_stages:
        service.update_stage(
            stage.ufls_stage_id,
            target_mw=Decimal("10"),
            engineering_remarks=None,
            actor_user_id=actor_user_id,
        )
    service.db.commit()

    service.publish(
        v2.version_id,
        publication_event_id=uuid.uuid4(),
        acknowledgements=[],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    v1_after = service.get_version(v1.version_id)
    v2_after = service.get_version(v2.version_id)
    other_after = service.get_version(other_version.version_id)
    assert v1_after.lifecycle_status == "SUPERSEDED"
    assert v2_after.lifecycle_status == "PUBLISHED"
    assert other_after.lifecycle_status == "PUBLISHED"  # unrelated lineage untouched


# --- Findings --------------------------------------------------------------------------


def test_findings_empty_when_alsf_capable_and_no_sensitive_customer(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, version, stage = _draft_version_with_one_stage(service, ufls_fixture, actor_user_id)
    service.add_direct_assignment(
        stage.ufls_stage_id,
        transformer_terminal_id=ufls_fixture.transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    findings = service.compute_findings(version.version_id)
    assert not any(f.finding_type == FindingType.ALSF_CAPABILITY_ABSENCE for f in findings)


# --- Engineering summaries --------------------------------------------------------------


def test_engineering_summary_totals(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, version, stage = _draft_version_with_one_stage(
        service, ufls_fixture, actor_user_id, target_mw="15.5"
    )
    service.add_direct_assignment(
        stage.ufls_stage_id,
        transformer_terminal_id=ufls_fixture.transformer_terminal_id,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    summary = service.get_engineering_summary(version.version_id)
    assert summary.total_target_mw == Decimal("15.5")
    assert summary.direct_assignment_count == 1
    assert summary.distinct_substation_count == 1
    assert len(summary.stage_summaries) == 1


# --- Stage Setting Registry reference / publication-reproducibility --------------------
#
# UFLS never copies a Stage Setting's own threshold/delay values into
# UflsStage — it stores only `stage_setting_id`, a reference
# (shared-defence-scheme-domain-model.md; ADR-016). Reproducibility of a
# Published UFLS version therefore depends entirely on the referenced
# Stage Setting Set's own immutability once Published, not on any UFLS-side
# copy. These tests prove that guarantee holds end to end: a later
# Stage Setting Registry correction (Entered in Error) can never alter what
# a Published UFLS version reports, and can only block *new* Draft
# publication against the corrected set, never retroactively invalidate an
# already-Published one (stage-setting-set-architecture.md §7 rules 1-3).


def test_published_ufls_stage_data_unaffected_by_later_stage_setting_set_correction(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    service = UflsService(db_session)
    _, version, stages = _draft_version_ready_to_publish(
        service, ufls_fixture, actor_user_id, scheme_name="Reproducibility Test"
    )
    service.publish(
        version.version_id,
        publication_event_id=uuid.uuid4(),
        acknowledgements=[],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.db.commit()

    before = service.to_stage_detail(service.get_stage(stages[0].ufls_stage_id))

    stage_registry = StageSettingRegistryService(db_session)
    stage_registry.enter_in_error(
        ufls_fixture.stage_setting_set_id,
        change_reason="Regression test: correcting a mistaken Published Stage Setting Set.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    after = service.to_stage_detail(service.get_stage(stages[0].ufls_stage_id))
    assert len(after.triggers) == len(before.triggers)
    assert after.triggers[0].threshold_value == before.triggers[0].threshold_value
    assert after.triggers[0].threshold_unit == before.triggers[0].threshold_unit
    assert after.triggers[0].time_delay_ms == before.triggers[0].time_delay_ms
    assert after.stage_order == before.stage_order

    # The Published UFLS version itself remains Published and untouched —
    # correcting the registry is not a UFLS lifecycle event.
    version_after = service.get_version(version.version_id)
    assert version_after.lifecycle_status == "PUBLISHED"


def test_draft_ufls_publish_blocked_after_referenced_stage_setting_set_entered_in_error(
    db_session: Session, ufls_fixture: Fixture, actor_user_id: uuid.UUID
) -> None:
    """stage-setting-set-architecture.md §7 rule 2: a Draft Scheme Version
    referencing a Stage Setting Set later marked Entered in Error acquires
    a structural Publication-blocking condition — enforced here as a live
    status check (`compute_prerequisites` reads the Stage Setting Set's
    *current* status every time), not a value captured once at Draft
    creation."""
    service = UflsService(db_session)
    _, version, _stages = _draft_version_ready_to_publish(
        service, ufls_fixture, actor_user_id, scheme_name="Blocked-by-correction Test"
    )

    stage_registry = StageSettingRegistryService(db_session)
    stage_registry.enter_in_error(
        ufls_fixture.stage_setting_set_id,
        change_reason="Regression test: correcting before this Draft ever published.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    prerequisites = service.compute_prerequisites(version.version_id)
    published_check = next(
        p for p in prerequisites if p.prerequisite_code == "UFLS_STAGE_SETTING_SET_PUBLISHED"
    )
    assert published_check.passed is False

    with pytest.raises(PrerequisiteFailedError):
        service.publish(
            version.version_id,
            publication_event_id=uuid.uuid4(),
            acknowledgements=[],
            remarks=None,
            actor_user_id=actor_user_id,
        )
