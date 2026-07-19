"""Service-layer tests for `EngineeringParameterService` — upsert
creation/update semantics, mandatory change_reason, per-key value
validation, audit history, and the read-only cross-module interface
future detectors (ADR-022) will consume.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.engineering_parameters.exceptions import (
    ChangeReasonRequiredError,
    InvalidParameterValueError,
    ParameterNotFoundError,
)
from app.modules.engineering_parameters.service import EngineeringParameterService

# --- Creation (first-ever value) -----------------------------------------------------


def test_set_value_creates_parameter_on_first_use(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    parameter = service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description="Global MW tolerance.",
        change_reason="Initial value.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    assert parameter.parameter_key == "mw_tolerance_percentage"
    assert parameter.value == "10"

    detail = service.get_parameter("mw_tolerance_percentage")
    assert detail is not None
    assert detail.value == "10"
    assert detail.unit == "percent"
    assert detail.updated_by is not None
    assert detail.updated_by.user_id == actor_user_id


def test_creation_is_audited_with_null_old_value(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description=None,
        change_reason="Initial value.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, total = service.list_audit_log("mw_tolerance_percentage", page=1, page_size=50)
    assert total == 1
    assert entries[0].old_value is None
    assert entries[0].new_value == "10"
    assert entries[0].change_reason == "Initial value."
    assert entries[0].changed_by is not None
    assert entries[0].changed_by.user_id == actor_user_id


# --- Update (subsequent value change) ------------------------------------------------


def test_set_value_updates_existing_parameter(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description=None,
        change_reason="Initial value.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    updated = service.set_parameter_value(
        "mw_tolerance_percentage",
        value="15",
        unit=None,
        description=None,
        change_reason="Widened after engineering review.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    assert updated.value == "15"
    # Preserved, not clobbered, since unit was omitted (None) on update.
    assert updated.unit == "percent"

    entries, total = service.list_audit_log("mw_tolerance_percentage", page=1, page_size=50)
    assert total == 2
    assert entries[0].old_value == "10"
    assert entries[0].new_value == "15"
    assert entries[0].change_reason == "Widened after engineering review."


def test_updating_to_the_same_value_does_not_create_a_new_audit_entry(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description=None,
        change_reason="Initial value.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit=None,
        description="Updated description only.",
        change_reason="Clarify description.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, total = service.list_audit_log("mw_tolerance_percentage", page=1, page_size=50)
    assert total == 1  # value unchanged -> no second audit row

    detail = service.get_parameter("mw_tolerance_percentage")
    assert detail is not None
    assert detail.description == "Updated description only."


# --- Validation -----------------------------------------------------------------------


def test_set_value_requires_non_empty_change_reason(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    with pytest.raises(ChangeReasonRequiredError):
        service.set_parameter_value(
            "mw_tolerance_percentage",
            value="10",
            unit="percent",
            description=None,
            change_reason="   ",
            actor_user_id=actor_user_id,
        )


def test_set_value_rejects_non_numeric_value_for_registered_parameter(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    with pytest.raises(InvalidParameterValueError):
        service.set_parameter_value(
            "mw_tolerance_percentage",
            value="not-a-number",
            unit="percent",
            description=None,
            change_reason="Initial value.",
            actor_user_id=actor_user_id,
        )


def test_set_value_rejects_out_of_range_percentage(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    with pytest.raises(InvalidParameterValueError):
        service.set_parameter_value(
            "mw_tolerance_percentage",
            value="150",
            unit="percent",
            description=None,
            change_reason="Initial value.",
            actor_user_id=actor_user_id,
        )
    with pytest.raises(InvalidParameterValueError):
        service.set_parameter_value(
            "mw_tolerance_percentage",
            value="0",
            unit="percent",
            description=None,
            change_reason="Initial value.",
            actor_user_id=actor_user_id,
        )


def test_set_value_rejects_empty_value(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = EngineeringParameterService(db_session)
    with pytest.raises(InvalidParameterValueError):
        service.set_parameter_value(
            "mw_tolerance_percentage",
            value="",
            unit="percent",
            description=None,
            change_reason="Initial value.",
            actor_user_id=actor_user_id,
        )


def test_unregistered_parameter_key_accepts_any_non_empty_string(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    """A future parameter with no registered numeric bounds is accepted as
    any non-empty string — module document §17: no validation invented
    ahead of a documented need."""
    service = EngineeringParameterService(db_session)
    parameter = service.set_parameter_value(
        "some_future_parameter",
        value="freeform-value",
        unit=None,
        description=None,
        change_reason="Test.",
        actor_user_id=actor_user_id,
    )
    assert parameter.value == "freeform-value"


# --- Not found --------------------------------------------------------------------------


def test_get_parameter_returns_none_for_unknown_key(db_session: Session) -> None:
    service = EngineeringParameterService(db_session)
    assert service.get_parameter("does_not_exist") is None


def test_list_audit_log_raises_for_unknown_key(db_session: Session) -> None:
    service = EngineeringParameterService(db_session)
    with pytest.raises(ParameterNotFoundError):
        service.list_audit_log("does_not_exist", page=1, page_size=50)


# --- Cross-module read interface (ADR-021 §13 / ADR-022) -----------------------------


def test_get_parameter_value_returns_current_value(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = EngineeringParameterService(db_session)
    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description=None,
        change_reason="Initial value.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    assert service.get_parameter_value("mw_tolerance_percentage") == "10"


def test_get_parameter_value_returns_none_for_unknown_key(db_session: Session) -> None:
    service = EngineeringParameterService(db_session)
    assert service.get_parameter_value("does_not_exist") is None


# --- Listing ----------------------------------------------------------------------------


def test_list_parameters(db_session: Session, actor_user_id: uuid.UUID) -> None:
    service = EngineeringParameterService(db_session)
    service.set_parameter_value(
        "mw_tolerance_percentage",
        value="10",
        unit="percent",
        description=None,
        change_reason="Initial value.",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    parameters = service.list_parameters()
    assert [p.parameter_key for p in parameters] == ["mw_tolerance_percentage"]
