"""Service-layer tests for `StageSettingRegistryService` — Draft
creation/editing, UFLS/UVLS scheme-type-specific validation, stage/trigger
CRUD (ADR-025), threshold monotonicity (via each stage's most severe
trigger), publication prerequisites and atomicity, the closed lifecycle
transition table, audit history, and decimal precision.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from app.modules.stage_setting_registry.exceptions import (
    DuplicateStageOrderError,
    DuplicateTriggerOrderError,
    DuplicateTriggerPairError,
    EmptyStageSettingSetPublicationError,
    EmptyStageTriggersPublicationError,
    EnterInErrorReasonRequiredError,
    InvalidLifecycleTransitionError,
    InvalidSchemeTypeError,
    InvalidThresholdValueError,
    InvalidTimeDelayError,
    RegionNotFoundError,
    RegionScopeNotAllowedError,
    ReorderSetMismatchError,
    ReorderTriggerSetMismatchError,
    StageSettingNotFoundError,
    StageSettingSetNotDraftError,
    StageSettingSetNotFoundError,
    StageSettingSetReferencedError,
    StageSettingTriggerNotFoundError,
    ThresholdMonotonicityError,
)
from app.modules.stage_setting_registry.service import StageSettingRegistryService

# --- Test helpers -----------------------------------------------------------------------


def _ufls_draft(service: StageSettingRegistryService, actor_user_id: uuid.UUID) -> uuid.UUID:
    stage_setting_set = service.create_draft(
        scheme_type="UFLS", description=None, actor_user_id=actor_user_id
    )
    return stage_setting_set.stage_setting_set_id


def _add_stage_with_trigger(
    service: StageSettingRegistryService,
    stage_setting_set_id: uuid.UUID,
    *,
    stage_order: int,
    threshold_value: float,
    time_delay_ms: int,
    region_scope_id: int | None = None,
    trigger_order: int = 1,
    actor_user_id: uuid.UUID,
):
    """Convenience: creates a stage with exactly one trigger — the shape
    almost every pre-ADR-025 test needs. Returns the stage (`StageSetting`)
    detail; the trigger itself is reachable via `.triggers[0]`."""
    stage = service.add_stage(
        stage_setting_set_id,
        stage_order=stage_order,
        region_scope_id=region_scope_id,
        actor_user_id=actor_user_id,
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=trigger_order,
        threshold_value=threshold_value,
        time_delay_ms=time_delay_ms,
        actor_user_id=actor_user_id,
    )
    return stage


# --- Draft creation -------------------------------------------------------------------


def test_create_ufls_draft(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UFLS", description="UFLS standard 5-stage design", actor_user_id=actor_user_id
    )
    db_session.commit()

    assert stage_setting_set.scheme_type == "UFLS"
    assert stage_setting_set.status == "DRAFT"

    detail = service.get_set(stage_setting_set.stage_setting_set_id)
    assert detail is not None
    assert detail.settings == []
    assert detail.created_by is not None
    assert detail.created_by.user_id == actor_user_id


def test_create_uvls_draft(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    assert stage_setting_set.scheme_type == "UVLS"


def test_create_draft_rejects_unsupported_scheme_type(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    with pytest.raises(InvalidSchemeTypeError):
        service.create_draft(scheme_type="EMLS", description=None, actor_user_id=actor_user_id)


def test_create_is_audited(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UFLS", description=None, actor_user_id=actor_user_id
    )
    db_session.commit()

    entries, total = service.list_audit_log(
        stage_setting_set.stage_setting_set_id, page=1, page_size=50
    )
    assert total == 1
    assert entries[0].action == "created"
    assert entries[0].subject_type == "STAGE_SETTING_SET"


# --- Metadata updates -------------------------------------------------------------------


def test_update_draft_metadata(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UFLS", description="Initial", actor_user_id=actor_user_id
    )
    db_session.commit()

    service.update_draft_metadata(
        stage_setting_set.stage_setting_set_id,
        description="Revised description",
        change_reason="Clarify design intent",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_set(stage_setting_set.stage_setting_set_id)
    assert detail is not None
    assert detail.description == "Revised description"


def test_update_metadata_requires_draft(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UFLS", description=None, actor_user_id=actor_user_id
    )
    _add_stage_with_trigger(
        service,
        stage_setting_set.stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set.stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.update_draft_metadata(
            stage_setting_set.stage_setting_set_id,
            description="Should fail",
            actor_user_id=actor_user_id,
        )


def test_get_set_returns_none_for_unknown_id(db_session: Session) -> None:
    service = StageSettingRegistryService(db_session)
    assert service.get_set(uuid.uuid4()) is None


def test_operations_on_unknown_set_raise_not_found(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    unknown_id = uuid.uuid4()
    with pytest.raises(StageSettingSetNotFoundError):
        service.update_draft_metadata(unknown_id, description="x", actor_user_id=actor_user_id)
    with pytest.raises(StageSettingSetNotFoundError):
        service.add_stage(
            unknown_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
        )
    with pytest.raises(StageSettingSetNotFoundError):
        service.publish(unknown_id, actor_user_id=actor_user_id)
    with pytest.raises(StageSettingSetNotFoundError):
        service.enter_in_error(unknown_id, change_reason="x", actor_user_id=actor_user_id)
    with pytest.raises(StageSettingSetNotFoundError):
        service.list_settings(unknown_id)
    with pytest.raises(StageSettingSetNotFoundError):
        service.list_audit_log(unknown_id, page=1, page_size=50)


# --- Stage addition — UFLS ------------------------------------------------------------


def test_add_ufls_stage(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)

    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    db_session.commit()

    assert stage.stage_order == 1
    assert stage.region_scope_id is None


def test_ufls_stage_rejects_region_scope(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)

    with pytest.raises(RegionScopeNotAllowedError):
        service.add_stage(
            stage_setting_set_id, stage_order=1, region_scope_id=1, actor_user_id=actor_user_id
        )


def test_stage_requires_draft_parent(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.add_stage(
            stage_setting_set_id, stage_order=2, region_scope_id=None, actor_user_id=actor_user_id
        )


def test_duplicate_stage_order_within_same_scope_rejected(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    with pytest.raises(DuplicateStageOrderError):
        service.add_stage(
            stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
        )


# --- Stage addition — UVLS, region scoping ---------------------------------------------


def test_uvls_stage_accepts_null_scope(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    stage = service.add_stage(
        stage_setting_set.stage_setting_set_id,
        stage_order=1,
        region_scope_id=None,
        actor_user_id=actor_user_id,
    )
    assert stage.region_scope_id is None


def test_uvls_stage_accepts_valid_region_scope(
    db_session: Session, actor_user_id: uuid.UUID, region_ids: dict[str, int]
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    stage = service.add_stage(
        stage_setting_set.stage_setting_set_id,
        stage_order=1,
        region_scope_id=region_ids["NORTH"],
        actor_user_id=actor_user_id,
    )
    assert stage.region_scope_id == region_ids["NORTH"]


def test_uvls_stage_rejects_unknown_region(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    with pytest.raises(RegionNotFoundError):
        service.add_stage(
            stage_setting_set.stage_setting_set_id,
            stage_order=1,
            region_scope_id=999999,
            actor_user_id=actor_user_id,
        )


def test_same_stage_order_allowed_across_different_uvls_region_scopes(
    db_session: Session, actor_user_id: uuid.UUID, region_ids: dict[str, int]
) -> None:
    """The whole point of per-scope uniqueness (module document §7 rule
    4): stage_order=1 may legitimately exist once in Region NORTH and once
    in Region SOUTH within the *same* Stage Setting Set."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    service.add_stage(
        stage_setting_set.stage_setting_set_id,
        stage_order=1,
        region_scope_id=region_ids["NORTH"],
        actor_user_id=actor_user_id,
    )
    stage_south = service.add_stage(
        stage_setting_set.stage_setting_set_id,
        stage_order=1,
        region_scope_id=region_ids["SOUTH"],
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert stage_south.stage_order == 1


# --- Stage update ---------------------------------------------------------------------


def test_update_stage_region_scope(
    db_session: Session, actor_user_id: uuid.UUID, region_ids: dict[str, int]
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    stage_setting_set_id = stage_setting_set.stage_setting_set_id
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    db_session.commit()

    service.update_stage(
        stage_setting_set_id,
        stage.stage_setting_id,
        region_scope_id=region_ids["NORTH"],
        change_reason="Scope correction",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    updated = service.get_setting(stage.stage_setting_id)
    assert updated is not None
    assert updated.region_scope_id == region_ids["NORTH"]


def test_update_stage_requires_draft_parent(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.update_stage(
            stage_setting_set_id,
            stage.stage_setting_id,
            region_scope_id=None,
            actor_user_id=actor_user_id,
        )


def test_update_unknown_stage_raises(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    with pytest.raises(StageSettingNotFoundError):
        service.update_stage(
            stage_setting_set_id, uuid.uuid4(), region_scope_id=None, actor_user_id=actor_user_id
        )


# --- Stage removal ----------------------------------------------------------------------


def test_remove_stage(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.remove_stage(stage_setting_set_id, stage.stage_setting_id, actor_user_id=actor_user_id)
    db_session.commit()

    assert service.list_settings(stage_setting_set_id) == []
    assert service.get_setting(stage.stage_setting_id) is None


def test_remove_stage_deletes_owned_triggers_explicitly(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """ADR-025: removing a stage must not orphan its triggers — no
    `ON DELETE CASCADE` (CLAUDE.md §11.7), so the service must delete them
    itself."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger_1 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    trigger_2 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.remove_stage(stage_setting_set_id, stage.stage_setting_id, actor_user_id=actor_user_id)
    db_session.commit()

    assert service.get_trigger(trigger_1.stage_setting_trigger_id) is None
    assert service.get_trigger(trigger_2.stage_setting_trigger_id) is None


def test_remove_stage_is_audited_and_survives_row_deletion(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    service.remove_stage(
        stage_setting_set_id,
        stage.stage_setting_id,
        change_reason="Data entry mistake",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, _total = service.list_audit_log(stage_setting_set_id, page=1, page_size=50)
    removal_entries = [
        e for e in entries if e.action == "removed" and e.subject_type == "STAGE_SETTING"
    ]
    assert len(removal_entries) == 1
    assert removal_entries[0].stage_setting_id == stage.stage_setting_id
    assert removal_entries[0].new_value is None


def test_remove_stage_requires_draft_parent(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.remove_stage(
            stage_setting_set_id, stage.stage_setting_id, actor_user_id=actor_user_id
        )


# --- Stage reordering ------------------------------------------------------------------


def test_reorder_stages(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    s1 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    s2 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=49.3,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    # Swap: s2 becomes stage_order 1, s1 becomes stage_order 2.
    service.reorder_stages(
        stage_setting_set_id,
        region_scope_id=None,
        ordered_stage_setting_ids=[s2.stage_setting_id, s1.stage_setting_id],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    reordered = service.list_settings(stage_setting_set_id)
    by_id = {s.stage_setting_id: s for s in reordered}
    assert by_id[s2.stage_setting_id].stage_order == 1
    assert by_id[s1.stage_setting_id].stage_order == 2


def test_reorder_stages_rejects_mismatched_id_set(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    with pytest.raises(ReorderSetMismatchError):
        service.reorder_stages(
            stage_setting_set_id,
            region_scope_id=None,
            ordered_stage_setting_ids=[uuid.uuid4()],
            actor_user_id=actor_user_id,
        )


def test_reorder_stages_is_audited_as_one_entry(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    s1 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    s2 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=49.3,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.reorder_stages(
        stage_setting_set_id,
        region_scope_id=None,
        ordered_stage_setting_ids=[s2.stage_setting_id, s1.stage_setting_id],
        change_reason="Swap priority",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, _total = service.list_audit_log(stage_setting_set_id, page=1, page_size=50)
    reorder_entries = [e for e in entries if e.action == "settings_reordered"]
    assert len(reorder_entries) == 1


def test_reorder_stages_scoped_to_one_region_group_at_a_time(
    db_session: Session, actor_user_id: uuid.UUID, region_ids: dict[str, int]
) -> None:
    """Reordering Region NORTH's own group must never touch Region
    SOUTH's own, independent ordering."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    stage_setting_set_id = stage_setting_set.stage_setting_set_id
    north_1 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=0.90,
        time_delay_ms=100,
        region_scope_id=region_ids["NORTH"],
        actor_user_id=actor_user_id,
    )
    north_2 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=0.85,
        time_delay_ms=200,
        region_scope_id=region_ids["NORTH"],
        actor_user_id=actor_user_id,
    )
    south_1 = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=0.88,
        time_delay_ms=150,
        region_scope_id=region_ids["SOUTH"],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.reorder_stages(
        stage_setting_set_id,
        region_scope_id=region_ids["NORTH"],
        ordered_stage_setting_ids=[north_2.stage_setting_id, north_1.stage_setting_id],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    by_id = {s.stage_setting_id: s for s in service.list_settings(stage_setting_set_id)}
    assert by_id[north_2.stage_setting_id].stage_order == 1
    assert by_id[north_1.stage_setting_id].stage_order == 2
    assert by_id[south_1.stage_setting_id].stage_order == 1  # untouched


# --- Triggers (ADR-025) ------------------------------------------------------------------


def test_add_single_trigger(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    assert trigger.threshold_unit == "Hz"
    assert Decimal(str(trigger.threshold_value)) == Decimal("49.5000")

    detail = service.get_setting(stage.stage_setting_id)
    assert detail is not None
    assert len(detail.triggers) == 1


def test_add_two_triggers_under_one_stage(db_session: Session, actor_user_id: uuid.UUID) -> None:
    """The worked UAT example: Stage 8 with a fast, low-delay trip and a
    slower backup trip — both belong to the same stage, never a second
    stage sharing the same stage_order."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=8, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_setting(stage.stage_setting_id)
    assert detail is not None
    assert detail.stage_order == 8
    assert len(detail.triggers) == 2
    ordered = sorted(detail.triggers, key=lambda t: t.trigger_order)
    assert Decimal(str(ordered[0].threshold_value)) == Decimal("48.1000")
    assert ordered[0].time_delay_ms == 0
    assert Decimal(str(ordered[1].threshold_value)) == Decimal("49.3000")
    assert ordered[1].time_delay_ms == 60000

    # Only one stage exists — the second trigger never created a second
    # StageSetting row sharing stage_order=8.
    all_settings = service.list_settings(stage_setting_set_id)
    assert len(all_settings) == 1


def test_trigger_requires_draft_parent(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=2,
            threshold_value=49.0,
            time_delay_ms=300,
            actor_user_id=actor_user_id,
        )


def test_add_trigger_rejects_non_positive_threshold(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    with pytest.raises(InvalidThresholdValueError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=1,
            threshold_value=0,
            time_delay_ms=200,
            actor_user_id=actor_user_id,
        )
    with pytest.raises(InvalidThresholdValueError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=1,
            threshold_value=-1,
            time_delay_ms=200,
            actor_user_id=actor_user_id,
        )


def test_add_trigger_rejects_negative_time_delay(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    with pytest.raises(InvalidTimeDelayError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=1,
            threshold_value=49.5,
            time_delay_ms=-1,
            actor_user_id=actor_user_id,
        )


def test_duplicate_trigger_order_within_same_stage_rejected(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    with pytest.raises(DuplicateTriggerOrderError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=1,
            threshold_value=49.3,
            time_delay_ms=60000,
            actor_user_id=actor_user_id,
        )


def test_duplicate_threshold_delay_pair_within_same_stage_rejected(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    with pytest.raises(DuplicateTriggerPairError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=2,
            threshold_value=48.1,
            time_delay_ms=0,
            actor_user_id=actor_user_id,
        )


def test_duplicate_pair_check_ignores_trigger_order(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """The pair-uniqueness rule is about (threshold, delay), independent
    of trigger_order — two different stages may reuse the same pair (no
    cross-stage rule), but the *same* stage may not."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage_a = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    stage_b = service.add_stage(
        stage_setting_set_id, stage_order=2, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage_a.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    # Same (threshold, delay) pair on a *different* stage — allowed.
    trigger_b = service.add_trigger(
        stage_setting_set_id,
        stage_b.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert Decimal(str(trigger_b.threshold_value)) == Decimal("48.1000")


def test_stage_order_unique_at_parent_level_regardless_of_trigger_count(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """A stage with several triggers still occupies exactly one
    stage_order — adding more triggers never creates a second StageSetting
    row, so stage_order uniqueness is completely unaffected by trigger
    count."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=8, region_scope_id=None, actor_user_id=actor_user_id
    )
    for order, (threshold, delay) in enumerate([(48.1, 0), (49.3, 60000), (49.6, 120000)], start=1):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=order,
            threshold_value=threshold,
            time_delay_ms=delay,
            actor_user_id=actor_user_id,
        )
    db_session.commit()

    with pytest.raises(DuplicateStageOrderError):
        service.add_stage(
            stage_setting_set_id, stage_order=8, region_scope_id=None, actor_user_id=actor_user_id
        )


def test_update_trigger_threshold_and_delay(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.update_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger.stage_setting_trigger_id,
        threshold_value=49.3,
        time_delay_ms=250,
        change_reason="Engineering revision",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    updated = service.get_setting(stage.stage_setting_id)
    assert updated is not None
    updated_trigger = updated.triggers[0]
    assert Decimal(str(updated_trigger.threshold_value)) == Decimal("49.3000")
    assert updated_trigger.time_delay_ms == 250


def test_update_trigger_requires_draft_parent(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.update_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger.stage_setting_trigger_id,
            threshold_value=1,
            actor_user_id=actor_user_id,
        )


def test_update_unknown_trigger_raises(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    with pytest.raises(StageSettingTriggerNotFoundError):
        service.update_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            uuid.uuid4(),
            threshold_value=1,
            actor_user_id=actor_user_id,
        )


def test_update_trigger_omitted_fields_are_unchanged(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.update_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger.stage_setting_trigger_id,
        time_delay_ms=300,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    updated = service.get_setting(stage.stage_setting_id)
    assert updated is not None
    updated_trigger = updated.triggers[0]
    assert Decimal(str(updated_trigger.threshold_value)) == Decimal("49.5000")  # unchanged
    assert updated_trigger.time_delay_ms == 300


def test_update_trigger_rejects_collision_with_another_triggers_pair(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    trigger_2 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(DuplicateTriggerPairError):
        service.update_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_2.stage_setting_trigger_id,
            threshold_value=48.1,
            time_delay_ms=0,
            actor_user_id=actor_user_id,
        )


def test_remove_trigger(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger_1 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    trigger_2 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.remove_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_1.stage_setting_trigger_id,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    remaining = service.list_triggers(stage_setting_set_id, stage.stage_setting_id)
    assert [t.stage_setting_trigger_id for t in remaining] == [trigger_2.stage_setting_trigger_id]


def test_remove_trigger_is_audited_and_survives_row_deletion(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    service.remove_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger.stage_setting_trigger_id,
        change_reason="Data entry mistake",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, _total = service.list_audit_log(stage_setting_set_id, page=1, page_size=50)
    removal_entries = [
        e for e in entries if e.action == "removed" and e.subject_type == "STAGE_SETTING_TRIGGER"
    ]
    assert len(removal_entries) == 1
    assert removal_entries[0].stage_setting_trigger_id == trigger.stage_setting_trigger_id
    assert removal_entries[0].new_value is None


def test_remove_trigger_requires_draft_parent(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.remove_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger.stage_setting_trigger_id,
            actor_user_id=actor_user_id,
        )


def test_reorder_triggers(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    t1 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    t2 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.reorder_triggers(
        stage_setting_set_id,
        stage.stage_setting_id,
        ordered_trigger_ids=[t2.stage_setting_trigger_id, t1.stage_setting_trigger_id],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    reordered = {
        t.stage_setting_trigger_id: t
        for t in service.list_triggers(stage_setting_set_id, stage.stage_setting_id)
    }
    assert reordered[t2.stage_setting_trigger_id].trigger_order == 1
    assert reordered[t1.stage_setting_trigger_id].trigger_order == 2


def test_reorder_triggers_rejects_mismatched_id_set(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    with pytest.raises(ReorderTriggerSetMismatchError):
        service.reorder_triggers(
            stage_setting_set_id,
            stage.stage_setting_id,
            ordered_trigger_ids=[uuid.uuid4()],
            actor_user_id=actor_user_id,
        )


def test_reorder_triggers_is_audited(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = service.add_stage(
        stage_setting_set_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    t1 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    t2 = service.add_trigger(
        stage_setting_set_id,
        stage.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.reorder_triggers(
        stage_setting_set_id,
        stage.stage_setting_id,
        ordered_trigger_ids=[t2.stage_setting_trigger_id, t1.stage_setting_trigger_id],
        change_reason="Swap priority",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, _total = service.list_audit_log(stage_setting_set_id, page=1, page_size=50)
    reorder_entries = [e for e in entries if e.action == "triggers_reordered"]
    assert len(reorder_entries) == 1


# --- Publication prerequisites and atomicity ----------------------------------------------


def test_publish_rejects_empty_set(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    with pytest.raises(EmptyStageSettingSetPublicationError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)


def test_publish_rejects_stage_with_zero_triggers(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """ADR-025 business rule 1: a Stage Setting Set with a stage that owns
    zero triggers may not be published, even if other stages are
    complete."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    # Stage 2 has no trigger at all.
    service.add_stage(
        stage_setting_set_id, stage_order=2, region_scope_id=None, actor_user_id=actor_user_id
    )
    db_session.commit()

    with pytest.raises(EmptyStageTriggersPublicationError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)

    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    assert detail.status == "DRAFT"


def test_publish_rejects_non_monotonic_thresholds(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.0,  # lower than stage 2 — violates "strictly decrease"
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(ThresholdMonotonicityError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)

    # Atomicity: a rejected publish must not have changed the status.
    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    assert detail.status == "DRAFT"


def test_publish_rejects_equal_thresholds(db_session: Session, actor_user_id: uuid.UUID) -> None:
    """Strictly decreasing — equal values across adjacent stages are not
    monotonic either."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=49.5,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(ThresholdMonotonicityError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)


def test_publish_success(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=49.0,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    assert detail.status == "PUBLISHED"


def test_publish_success_with_multiple_triggers_per_stage(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """The worked UAT example published end-to-end: Stage 8 with two
    triggers (48.1 Hz/0 ms and 49.3 Hz/60,000 ms) — monotonicity against
    Stage 7 is evaluated using Stage 8's own most severe (lowest) trigger,
    48.1 Hz."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=7,
        threshold_value=48.3,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    stage_8 = service.add_stage(
        stage_setting_set_id, stage_order=8, region_scope_id=None, actor_user_id=actor_user_id
    )
    service.add_trigger(
        stage_setting_set_id,
        stage_8.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    service.add_trigger(
        stage_setting_set_id,
        stage_8.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    assert detail.status == "PUBLISHED"


def test_publish_rejects_when_most_severe_trigger_breaks_monotonicity(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """Even though Stage 8 owns a trigger (49.3 Hz) numerically higher
    than Stage 7's single trigger (48.3 Hz), publication must still be
    rejected — Stage 8's *most severe* trigger (48.1 Hz) is what
    monotonicity compares, and if that stops being lower than Stage 7's,
    it's still a violation; this test instead breaks it by giving Stage 8
    a most-severe trigger that is not lower than Stage 7's."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=7,
        threshold_value=48.0,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    stage_8 = service.add_stage(
        stage_setting_set_id, stage_order=8, region_scope_id=None, actor_user_id=actor_user_id
    )
    # Stage 8's most severe (lowest) trigger is 49.3 — not lower than
    # Stage 7's 48.0, so monotonicity is violated despite Stage 8 owning
    # multiple triggers.
    service.add_trigger(
        stage_setting_set_id,
        stage_8.stage_setting_id,
        trigger_order=1,
        threshold_value=49.3,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    service.add_trigger(
        stage_setting_set_id,
        stage_8.stage_setting_id,
        trigger_order=2,
        threshold_value=49.6,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(ThresholdMonotonicityError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)


def test_publish_uvls_validates_monotonicity_within_each_region_scope_independently(
    db_session: Session, actor_user_id: uuid.UUID, region_ids: dict[str, int]
) -> None:
    """Region NORTH's own thresholds must be independently monotonic;
    Region SOUTH's own values are compared only against each other, never
    against NORTH's."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    stage_setting_set_id = stage_setting_set.stage_setting_set_id
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=0.95,
        time_delay_ms=100,
        region_scope_id=region_ids["NORTH"],
        actor_user_id=actor_user_id,
    )
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=0.90,
        time_delay_ms=200,
        region_scope_id=region_ids["NORTH"],
        actor_user_id=actor_user_id,
    )
    # SOUTH's own, unrelated, independently-monotonic sequence — even
    # though its own stage_order=1 threshold (0.80) is lower than NORTH's
    # stage_order=2 threshold (0.90), that comparison is never made.
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=0.80,
        time_delay_ms=100,
        region_scope_id=region_ids["SOUTH"],
        actor_user_id=actor_user_id,
    )
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=2,
        threshold_value=0.70,
        time_delay_ms=200,
        region_scope_id=region_ids["SOUTH"],
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    assert detail.status == "PUBLISHED"


def test_multiple_published_sets_of_the_same_scheme_type_may_coexist(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """module document §6: Published Stage Setting Sets are "referenceable
    by any number of Scheme Versions... concurrently or across time" — no
    "only one Published set per scheme type" invariant exists (unlike
    Scheme Version's own Active-supersession rule), so no row-locking or
    uniqueness constraint should ever prevent this."""
    service = StageSettingRegistryService(db_session)

    def _published_ufls_set() -> uuid.UUID:
        set_id = _ufls_draft(service, actor_user_id)
        _add_stage_with_trigger(
            service,
            set_id,
            stage_order=1,
            threshold_value=49.5,
            time_delay_ms=100,
            actor_user_id=actor_user_id,
        )
        service.publish(set_id, actor_user_id=actor_user_id)
        return set_id

    first_id = _published_ufls_set()
    second_id = _published_ufls_set()
    db_session.commit()

    published = service.list_sets(scheme_type="UFLS", status="PUBLISHED")
    published_ids = {s.stage_setting_set_id for s in published}
    assert {first_id, second_id} <= published_ids


# --- Lifecycle transitions ---------------------------------------------------------------


def test_published_set_is_immutable(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.update_draft_metadata(
            stage_setting_set_id, description="nope", actor_user_id=actor_user_id
        )
    with pytest.raises(StageSettingSetNotDraftError):
        service.add_stage(
            stage_setting_set_id, stage_order=2, region_scope_id=None, actor_user_id=actor_user_id
        )
    with pytest.raises(StageSettingSetNotDraftError):
        service.remove_stage(
            stage_setting_set_id, stage.stage_setting_id, actor_user_id=actor_user_id
        )
    with pytest.raises(StageSettingSetNotDraftError):
        service.add_trigger(
            stage_setting_set_id,
            stage.stage_setting_id,
            trigger_order=2,
            threshold_value=1,
            time_delay_ms=0,
            actor_user_id=actor_user_id,
        )


def test_publish_twice_is_invalid_transition(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(InvalidLifecycleTransitionError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)


def test_enter_in_error_requires_published(db_session: Session, actor_user_id: uuid.UUID) -> None:
    """Entered-in-Error is reachable only from Published, never directly
    from Draft (ADR-016's own "should never have been published"
    framing)."""
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)

    with pytest.raises(InvalidLifecycleTransitionError):
        service.enter_in_error(
            stage_setting_set_id, change_reason="Mistake", actor_user_id=actor_user_id
        )


def test_enter_in_error_requires_non_empty_reason(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(EnterInErrorReasonRequiredError):
        service.enter_in_error(
            stage_setting_set_id, change_reason="   ", actor_user_id=actor_user_id
        )


def test_enter_in_error_success_and_is_terminal(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    service.enter_in_error(
        stage_setting_set_id, change_reason="Data entry mistake", actor_user_id=actor_user_id
    )
    db_session.commit()

    detail = service.get_set(stage_setting_set_id)
    assert detail is not None
    assert detail.status == "ENTERED_IN_ERROR"

    # Terminal — no further transition permitted.
    with pytest.raises(InvalidLifecycleTransitionError):
        service.enter_in_error(
            stage_setting_set_id, change_reason="Again", actor_user_id=actor_user_id
        )
    with pytest.raises(InvalidLifecycleTransitionError):
        service.publish(stage_setting_set_id, actor_user_id=actor_user_id)


def test_enter_in_error_is_audited_with_reason(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    db_session.commit()

    service.enter_in_error(
        stage_setting_set_id, change_reason="Data entry mistake", actor_user_id=actor_user_id
    )
    db_session.commit()

    entries, _total = service.list_audit_log(stage_setting_set_id, page=1, page_size=50)
    eie_entries = [e for e in entries if e.action == "entered_in_error"]
    assert len(eie_entries) == 1
    assert eie_entries[0].change_reason == "Data entry mistake"
    assert eie_entries[0].old_value == "PUBLISHED"
    assert eie_entries[0].new_value == "ENTERED_IN_ERROR"


def test_entered_in_error_is_immutable(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session)
    stage_setting_set_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        stage_setting_set_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(stage_setting_set_id, actor_user_id=actor_user_id)
    service.enter_in_error(
        stage_setting_set_id, change_reason="Mistake", actor_user_id=actor_user_id
    )
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.update_draft_metadata(
            stage_setting_set_id, description="nope", actor_user_id=actor_user_id
        )


# --- Listing / filtering --------------------------------------------------------------


def test_list_sets_filters_by_scheme_type_and_status(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session)
    ufls_id = _ufls_draft(service, actor_user_id)
    uvls_set = service.create_draft(
        scheme_type="UVLS", description=None, actor_user_id=actor_user_id
    )
    db_session.commit()

    ufls_only = service.list_sets(scheme_type="UFLS")
    assert {s.stage_setting_set_id for s in ufls_only} == {ufls_id}

    draft_only = service.list_sets(status="DRAFT")
    assert {ufls_id, uvls_set.stage_setting_set_id} <= {s.stage_setting_set_id for s in draft_only}


def test_list_published_service_interface(db_session: Session, actor_user_id: uuid.UUID) -> None:
    """ADR-020 §11's own read-only interface for a future UFLS/UVLS
    Engineering Workspace to consume — no consumer exists yet, but the
    interface itself is already usable in-process."""
    service = StageSettingRegistryService(db_session)
    draft_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        draft_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(draft_id, actor_user_id=actor_user_id)
    unpublished_id = _ufls_draft(service, actor_user_id)
    db_session.commit()

    published = service.list_published(scheme_type="UFLS")
    published_ids = {s.stage_setting_set_id for s in published}
    assert draft_id in published_ids
    assert unpublished_id not in published_ids
    published_set = next(s for s in published if s.stage_setting_set_id == draft_id)
    assert len(published_set.settings[0].triggers) == 1


def test_list_published_rejects_unsupported_scheme_type(db_session: Session) -> None:
    service = StageSettingRegistryService(db_session)
    with pytest.raises(InvalidSchemeTypeError):
        service.list_published(scheme_type="EMLS")


# --- Draft deletion (ADR-024, extended by ADR-025) ---------------------------------------
#
# `reference_checkers={}` injects zero scheme-module checkers (mirrors
# `StageSettingRegistryService.__init__`'s own documented test-only
# injection seam) -- these tests exercise `delete_draft`'s own deletion/
# audit/lifecycle logic in isolation, independent of which real scheme
# module (if any) would supply a reference count. A fake checker is
# injected separately to test the blocking behaviour itself. The real,
# end-to-end UFLS integration (a genuine cross-module reference blocking
# deletion) lives in app/modules/ufls/tests/test_service.py, since it
# needs a full UFLS fixture.


class _FakeReferenceChecker:
    def __init__(self, count: int) -> None:
        self._count = count

    def count_references(self, stage_setting_set_id: uuid.UUID) -> int:
        return self._count


def test_delete_empty_draft_succeeds(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session, reference_checkers={})
    draft_id = _ufls_draft(service, actor_user_id)
    db_session.commit()

    service.delete_draft(draft_id, actor_user_id=actor_user_id)
    db_session.commit()

    assert service.get_set(draft_id) is None


def test_delete_draft_with_stages_and_triggers_deletes_all_children_and_parent(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session, reference_checkers={})
    draft_id = _ufls_draft(service, actor_user_id)
    stage_1 = service.add_stage(
        draft_id, stage_order=1, region_scope_id=None, actor_user_id=actor_user_id
    )
    trigger_1a = service.add_trigger(
        draft_id,
        stage_1.stage_setting_id,
        trigger_order=1,
        threshold_value=48.1,
        time_delay_ms=0,
        actor_user_id=actor_user_id,
    )
    trigger_1b = service.add_trigger(
        draft_id,
        stage_1.stage_setting_id,
        trigger_order=2,
        threshold_value=49.3,
        time_delay_ms=60000,
        actor_user_id=actor_user_id,
    )
    stage_2 = _add_stage_with_trigger(
        service,
        draft_id,
        stage_order=2,
        threshold_value=49.0,
        time_delay_ms=200,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.delete_draft(draft_id, actor_user_id=actor_user_id)
    db_session.commit()

    assert service.get_set(draft_id) is None
    assert service.get_setting(stage_1.stage_setting_id) is None
    assert service.get_setting(stage_2.stage_setting_id) is None
    assert service.get_trigger(trigger_1a.stage_setting_trigger_id) is None
    assert service.get_trigger(trigger_1b.stage_setting_trigger_id) is None


def test_delete_draft_writes_audit_entry_with_identifying_metadata(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(db_session, reference_checkers={})
    stage_setting_set = service.create_draft(
        scheme_type="UFLS", description="Deletable Draft", actor_user_id=actor_user_id
    )
    draft_id = stage_setting_set.stage_setting_set_id
    _add_stage_with_trigger(
        service,
        draft_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.delete_draft(
        draft_id, change_reason="Wrong scheme type chosen", actor_user_id=actor_user_id
    )
    db_session.commit()

    # The set no longer exists, so its own audit-log endpoint can't be
    # used (it requires `_require_set`) -- query the repository directly,
    # exactly as a future audit-log UI reading a deleted subject's own
    # history would need to (module docstring's own documented pattern).
    entries, total = service.repo.list_audit_log(draft_id, offset=0, limit=10)
    # "created" (set) + "created" (stage) + "created" (trigger) + "deleted" (set).
    assert total == 4
    deleted_entry = next(e for e in entries if e.action == "deleted")
    assert deleted_entry.subject_type == "STAGE_SETTING_SET"
    assert deleted_entry.stage_setting_set_id == draft_id
    assert deleted_entry.changed_by_user_id == actor_user_id
    assert deleted_entry.change_reason == "Wrong scheme type chosen"
    assert "scheme_type=UFLS" in deleted_entry.old_value
    assert "description=Deletable Draft" in deleted_entry.old_value
    assert "setting_count=1" in deleted_entry.old_value
    assert "trigger_count=1" in deleted_entry.old_value
    assert deleted_entry.new_value is None


def test_delete_published_rejected(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session, reference_checkers={})
    draft_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        draft_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(draft_id, actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.delete_draft(draft_id, actor_user_id=actor_user_id)

    # Never physically deleted -- remains a permanent engineering record.
    assert service.get_set(draft_id) is not None


def test_delete_entered_in_error_rejected(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session, reference_checkers={})
    draft_id = _ufls_draft(service, actor_user_id)
    _add_stage_with_trigger(
        service,
        draft_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    service.publish(draft_id, actor_user_id=actor_user_id)
    service.enter_in_error(draft_id, change_reason="Mistake", actor_user_id=actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetNotDraftError):
        service.delete_draft(draft_id, actor_user_id=actor_user_id)

    assert service.get_set(draft_id) is not None


def test_delete_missing_set_rejected(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = StageSettingRegistryService(db_session, reference_checkers={})
    with pytest.raises(StageSettingSetNotFoundError):
        service.delete_draft(uuid.uuid4(), actor_user_id=actor_user_id)


def test_delete_blocked_when_reference_checker_reports_references(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(
        db_session, reference_checkers={"UFLS": _FakeReferenceChecker(count=2)}
    )
    draft_id = _ufls_draft(service, actor_user_id)
    db_session.commit()

    with pytest.raises(StageSettingSetReferencedError):
        service.delete_draft(draft_id, actor_user_id=actor_user_id)

    # Blocked before any deletion was attempted -- the set is untouched.
    assert service.get_set(draft_id) is not None


def test_delete_not_blocked_when_reference_checker_reports_zero(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = StageSettingRegistryService(
        db_session, reference_checkers={"UFLS": _FakeReferenceChecker(count=0)}
    )
    draft_id = _ufls_draft(service, actor_user_id)
    db_session.commit()

    service.delete_draft(draft_id, actor_user_id=actor_user_id)
    db_session.commit()

    assert service.get_set(draft_id) is None


def test_delete_only_checks_the_matching_scheme_types_own_checker(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """A UVLS-registered checker reporting references must never block
    deletion of a UFLS set -- `delete_draft` looks up the checker keyed by
    the set's own `scheme_type` only."""
    service = StageSettingRegistryService(
        db_session, reference_checkers={"UVLS": _FakeReferenceChecker(count=99)}
    )
    draft_id = _ufls_draft(service, actor_user_id)
    db_session.commit()

    service.delete_draft(draft_id, actor_user_id=actor_user_id)
    db_session.commit()

    assert service.get_set(draft_id) is None


def test_delete_draft_rollback_preserves_everything_if_not_committed(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """`delete_draft` is flush-only, never commits (mirrors every other
    module's own established transaction-boundary discipline) -- if the
    caller rolls back instead of committing, the set, its stages, its
    triggers, and the audit entry must all still exist, exactly as if
    deletion had never been attempted."""
    service = StageSettingRegistryService(db_session, reference_checkers={})
    draft_id = _ufls_draft(service, actor_user_id)
    stage = _add_stage_with_trigger(
        service,
        draft_id,
        stage_order=1,
        threshold_value=49.5,
        time_delay_ms=100,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.delete_draft(draft_id, actor_user_id=actor_user_id)
    db_session.rollback()

    assert service.get_set(draft_id) is not None
    reloaded = service.get_setting(stage.stage_setting_id)
    assert reloaded is not None
    assert len(reloaded.triggers) == 1
    entries, total = service.repo.list_audit_log(draft_id, offset=0, limit=10)
    assert not any(e.action == "deleted" for e in entries)
