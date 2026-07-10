"""Service-layer tests for `AutomaticLoadSheddingFunctionalityService` —
creation/validation, uniqueness, the decommission lifecycle, metadata
updates, audit history, bay-identity display, Available/Assigned/
Decommissioned status computation, and the candidate/capability query
interfaces future UFLS/UVLS modules will consume.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.automatic_load_shedding_functionality.exceptions import (
    CircuitTerminalNotFoundError,
    DecommissionReasonRequiredError,
    FunctionalityDecommissionedImmutableError,
    FunctionalityNotFoundError,
    NoFunctionAssignedError,
    TerminalAlreadyHasFunctionalityError,
    TransformerTerminalNotFoundError,
    ValidationAppError,
)
from app.modules.automatic_load_shedding_functionality.service import (
    AutomaticLoadSheddingFunctionalityService,
)
from app.modules.automatic_load_shedding_functionality.tests.conftest import (
    CircuitTerminals,
    TransformerTerminals,
)

# --- Creation and validation --------------------------------------------------------


def test_create_circuit_terminal_functionality(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    # Status Model Refinement: every new record starts ACTIVE (raw), which
    # always displays as Available (no assigned_terminal_ids supplied).
    assert functionality.lifecycle_status == "ACTIVE"
    assert functionality.ufls_function is True
    assert functionality.uvls_function is False

    detail = service.get_detail(functionality.id)
    assert detail is not None
    assert detail.status == "AVAILABLE"
    assert detail.substation_mnemonic == "PKLG"
    assert detail.target_type == "CIRCUIT_TERMINAL"
    assert detail.bay_label.startswith("Line ")


def test_create_transformer_terminal_functionality(
    db_session: Session, transformer_terminals: TransformerTerminals, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=transformer_terminals.hv_terminal_id,
        ufls_function=False,
        uvls_function=True,
        relay_make="ABB",
        relay_model="REF615",
        remarks="Commissioned 2026",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_detail(functionality.id)
    assert detail is not None
    assert detail.target_type == "TRANSFORMER_TERMINAL"
    # HV side is 500kV -> "XGT" prefix (TNB short-name convention).
    assert detail.bay_label == "Transformer XGT1"
    assert detail.relay_make == "ABB"
    assert detail.status == "AVAILABLE"


def test_both_ufls_and_uvls_true_on_same_terminal_is_allowed(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    """Confirmed engineering rule: a single bay terminal can support both
    UFLS and UVLS."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=True,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert functionality.ufls_function is True
    assert functionality.uvls_function is True


def test_create_with_no_function_raises(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(NoFunctionAssignedError):
        service.create(
            target_type="CIRCUIT_TERMINAL",
            circuit_terminal_id=circuit_terminals.pklg_terminal_id,
            transformer_terminal_id=None,
            ufls_function=False,
            uvls_function=False,
            relay_make=None,
            relay_model=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_create_with_unknown_circuit_terminal_raises(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(CircuitTerminalNotFoundError):
        service.create(
            target_type="CIRCUIT_TERMINAL",
            circuit_terminal_id=uuid.uuid4(),
            transformer_terminal_id=None,
            ufls_function=True,
            uvls_function=False,
            relay_make=None,
            relay_model=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_create_with_unknown_transformer_terminal_raises(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(TransformerTerminalNotFoundError):
        service.create(
            target_type="TRANSFORMER_TERMINAL",
            circuit_terminal_id=None,
            transformer_terminal_id=uuid.uuid4(),
            ufls_function=True,
            uvls_function=False,
            relay_make=None,
            relay_model=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_create_with_both_terminal_ids_raises(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    transformer_terminals: TransformerTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    """Module document §9 rule 1 / §11's database XOR — exactly one target
    terminal per record."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(ValidationAppError):
        service.create(
            target_type="CIRCUIT_TERMINAL",
            circuit_terminal_id=circuit_terminals.pklg_terminal_id,
            transformer_terminal_id=transformer_terminals.hv_terminal_id,
            ufls_function=True,
            uvls_function=False,
            relay_make=None,
            relay_model=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_second_active_record_for_same_terminal_raises(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    """Module document §9 rule 2 / §11 — at most one non-decommissioned
    record per terminal."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(TerminalAlreadyHasFunctionalityError):
        service.create(
            target_type="CIRCUIT_TERMINAL",
            circuit_terminal_id=circuit_terminals.pklg_terminal_id,
            transformer_terminal_id=None,
            ufls_function=False,
            uvls_function=True,
            relay_make=None,
            relay_model=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_creation_writes_audit_log_entry(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    """Module document §14 explicitly lists "created" as a mandatory audit
    event for this module (unlike Substation Registry's own choice)."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, total = service.list_audit_log(functionality.id, page=1, page_size=50)
    assert total == 1
    assert entries[0].field_name == "lifecycle_status"
    assert entries[0].old_value is None
    assert entries[0].new_value == "ACTIVE"


# --- Bay identity display (Complete Engineering Identity Display) -------------------


def test_bay_label_distinguishes_ambiguous_circuit_terminals(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    second_circuit_terminals: CircuitTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    """Two parallel circuits between the same pair of substations, at the
    same voltage level, must never be displayed with the same bay_label —
    the engineer must be able to identify the exact terminal."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    first = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    second = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=second_circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    first_detail = service.get_detail(first.id)
    second_detail = service.get_detail(second.id)
    assert first_detail is not None
    assert second_detail is not None
    assert first_detail.substation_mnemonic == second_detail.substation_mnemonic
    assert first_detail.voltage_level_label == second_detail.voltage_level_label
    assert first_detail.bay_label != second_detail.bay_label


def test_bay_label_distinguishes_ambiguous_transformer_terminals(
    db_session: Session,
    transformer_terminals: TransformerTerminals,
    second_transformer_terminals: TransformerTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    """Two transformers at the same substation and the same HV voltage
    level (T1 vs T2) must never be displayed with the same bay_label."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    first = service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=transformer_terminals.hv_terminal_id,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    second = service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=second_transformer_terminals.hv_terminal_id,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    first_detail = service.get_detail(first.id)
    second_detail = service.get_detail(second.id)
    assert first_detail is not None
    assert second_detail is not None
    assert first_detail.substation_mnemonic == second_detail.substation_mnemonic
    assert first_detail.voltage_level_label == second_detail.voltage_level_label
    assert first_detail.bay_label != second_detail.bay_label
    # HV side is 500kV -> "XGT" prefix (TNB short-name convention).
    assert first_detail.bay_label == "Transformer XGT1"
    assert second_detail.bay_label == "Transformer XGT2"


# --- Status computation: Available / Assigned / Decommissioned ----------------------


@pytest.fixture()
def active_functionality_id(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> uuid.UUID:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return functionality.id


def test_current_phase_every_non_decommissioned_record_is_available(
    db_session: Session, active_functionality_id: uuid.UUID
) -> None:
    """Current Phase Behaviour (module document): UFLS/UVLS do not exist
    yet, so no caller supplies `assigned_terminal_ids` — every
    non-decommissioned record must display as Available, never Assigned."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    detail = service.get_detail(active_functionality_id)
    assert detail is not None
    assert detail.status == "AVAILABLE"

    items, _total = service.list_functionality(page=1, page_size=50)
    assert all(item.status in ("AVAILABLE", "DECOMMISSIONED") for item in items)


def test_assigned_status_is_computed_from_supplied_assigned_terminal_ids(
    db_session: Session,
    active_functionality_id: uuid.UUID,
    circuit_terminals: CircuitTerminals,
) -> None:
    """Future Integration Contract: a caller (a future UFLS/UVLS module)
    supplies the terminal IDs it currently has assigned; this module
    computes Assigned from that set alone, never by querying UFLS/UVLS's
    own tables (CLAUDE.md A1)."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)

    not_assigned = service.get_detail(active_functionality_id, assigned_terminal_ids=set())
    assert not_assigned is not None
    assert not_assigned.status == "AVAILABLE"

    assigned = service.get_detail(
        active_functionality_id,
        assigned_terminal_ids={circuit_terminals.pklg_terminal_id},
    )
    assert assigned is not None
    assert assigned.status == "ASSIGNED"

    # A different terminal being assigned must not affect this one.
    unaffected = service.get_detail(
        active_functionality_id,
        assigned_terminal_ids={uuid.uuid4()},
    )
    assert unaffected is not None
    assert unaffected.status == "AVAILABLE"


def test_list_functionality_filters_by_computed_status(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    transformer_terminals: TransformerTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    available_one = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    assigned_one = service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=transformer_terminals.hv_terminal_id,
        ufls_function=False,
        uvls_function=True,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    assigned_terminal_ids = {transformer_terminals.hv_terminal_id}

    available_items, available_total = service.list_functionality(
        page=1, page_size=50, status="AVAILABLE", assigned_terminal_ids=assigned_terminal_ids
    )
    assert available_total == 1
    assert available_items[0].id == available_one.id

    assigned_items, assigned_total = service.list_functionality(
        page=1, page_size=50, status="ASSIGNED", assigned_terminal_ids=assigned_terminal_ids
    )
    assert assigned_total == 1
    assert assigned_items[0].id == assigned_one.id


def test_decommissioned_record_always_displays_decommissioned_even_if_assigned(
    db_session: Session,
    active_functionality_id: uuid.UUID,
    circuit_terminals: CircuitTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.decommission(
        active_functionality_id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    db_session.commit()

    detail = service.get_detail(
        active_functionality_id,
        assigned_terminal_ids={circuit_terminals.pklg_terminal_id},
    )
    assert detail is not None
    assert detail.status == "DECOMMISSIONED"


# --- Lifecycle: decommission (the only remaining transition) ------------------------


def test_decommission_transitions_lifecycle_status(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    decommissioned = service.decommission(
        active_functionality_id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    assert decommissioned.lifecycle_status == "DECOMMISSIONED"


def test_decommission_without_reason_raises(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(DecommissionReasonRequiredError):
        service.decommission(
            active_functionality_id, change_reason=None, actor_user_id=actor_user_id
        )


def test_decommissioning_an_already_decommissioned_record_raises_immutable_error(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    """Decommissioning is a one-way, terminal transition — a second
    decommission attempt is rejected outright, not silently accepted as an
    idempotent no-op, since it would misrepresent an already-immutable
    historical fact (module document §8, §18)."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.decommission(
        active_functionality_id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    with pytest.raises(FunctionalityDecommissionedImmutableError):
        service.decommission(
            active_functionality_id,
            change_reason="Bay dismantled again",
            actor_user_id=actor_user_id,
        )


def test_decommissioned_record_is_immutable_to_metadata_edits(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.decommission(
        active_functionality_id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    with pytest.raises(FunctionalityDecommissionedImmutableError):
        service.update_metadata(
            active_functionality_id, remarks="trying to edit", actor_user_id=actor_user_id
        )


def test_decommission_on_unknown_id_raises_not_found(
    db_session: Session, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(FunctionalityNotFoundError):
        service.decommission(uuid.uuid4(), change_reason="reason", actor_user_id=actor_user_id)


def test_decommission_writes_audit_log_entry_with_reason(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.decommission(
        active_functionality_id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    db_session.commit()

    entries, total = service.list_audit_log(active_functionality_id, page=1, page_size=50)
    assert total == 2  # created + decommissioned
    decommission_entry = next(e for e in entries if e.new_value == "DECOMMISSIONED")
    assert decommission_entry.field_name == "lifecycle_status"
    assert decommission_entry.old_value == "ACTIVE"
    assert decommission_entry.change_reason == "Bay dismantled"


# --- Metadata updates ----------------------------------------------------------------


def test_update_metadata_audits_each_changed_field(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.update_metadata(
        active_functionality_id,
        uvls_function=True,
        relay_make="Siemens",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_detail(active_functionality_id)
    assert detail is not None
    assert detail.uvls_function is True
    assert detail.relay_make == "Siemens"

    entries, total = service.list_audit_log(active_functionality_id, page=1, page_size=50)
    field_names = {e.field_name for e in entries}
    assert "uvls_function" in field_names
    assert "relay_make" in field_names


def test_update_metadata_cannot_remove_last_function(
    db_session: Session, active_functionality_id: uuid.UUID, actor_user_id: uuid.UUID
) -> None:
    """`active_functionality_id` starts with ufls_function=True,
    uvls_function=False — turning ufls_function off with nothing else true
    must be rejected (module document §9 rule 3)."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(NoFunctionAssignedError):
        service.update_metadata(
            active_functionality_id, ufls_function=False, actor_user_id=actor_user_id
        )


# --- Candidate / capability queries (module document §13) ---------------------------


def test_is_ufls_capable_and_is_uvls_capable(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    # Created directly ACTIVE (Status Model Refinement) — immediately
    # capable, regardless of Available/Assigned display status.
    assert service.is_ufls_capable(circuit_terminal_id=circuit_terminals.pklg_terminal_id) is True
    assert service.is_uvls_capable(circuit_terminal_id=circuit_terminals.pklg_terminal_id) is False

    service.decommission(
        functionality.id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    db_session.commit()

    assert service.is_ufls_capable(circuit_terminal_id=circuit_terminals.pklg_terminal_id) is False


def test_capability_check_for_unregistered_terminal_is_false_not_error(
    db_session: Session,
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    assert service.is_ufls_capable(circuit_terminal_id=uuid.uuid4()) is False
    assert service.is_uvls_capable(transformer_terminal_id=uuid.uuid4()) is False


def test_list_candidate_terminals_filters_by_scheme_type_and_lifecycle_status(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    transformer_terminals: TransformerTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    ufls_only = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    uvls_only = service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=transformer_terminals.hv_terminal_id,
        ufls_function=False,
        uvls_function=True,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    ufls_candidates = service.list_candidate_terminals(scheme_type="UFLS")
    assert {c.id for c in ufls_candidates} == {ufls_only.id}

    uvls_candidates = service.list_candidate_terminals(scheme_type="UVLS")
    assert {c.id for c in uvls_candidates} == {uvls_only.id}


def test_list_candidate_terminals_excludes_decommissioned(
    db_session: Session, circuit_terminals: CircuitTerminals, actor_user_id: uuid.UUID
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    assert len(service.list_candidate_terminals(scheme_type="UFLS")) == 1

    service.decommission(
        functionality.id, change_reason="Bay dismantled", actor_user_id=actor_user_id
    )
    db_session.commit()

    # Decommissioned — must never appear as a candidate.
    assert service.list_candidate_terminals(scheme_type="UFLS") == []


def test_list_candidate_terminals_rejects_emls(db_session: Session) -> None:
    """Module document §4, §9 rule 4 — EMLS is never a valid scheme_type."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    with pytest.raises(ValidationAppError):
        service.list_candidate_terminals(scheme_type="EMLS")


def test_list_candidate_terminals_filters_by_substation(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    substation_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    matching = service.list_candidate_terminals(
        scheme_type="UFLS", substation_id=substation_ids["PKLG"]
    )
    assert len(matching) == 1

    non_matching = service.list_candidate_terminals(
        scheme_type="UFLS", substation_id=substation_ids["IGBK"]
    )
    assert non_matching == []


def test_list_assigned_and_available_partitions_by_caller_supplied_set(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    transformer_terminals: TransformerTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    """Module document §13 — this module never queries UFLS/UVLS tables
    itself; the caller supplies the currently-assigned terminal set."""
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    assigned_functionality = service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    available_functionality = service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=transformer_terminals.hv_terminal_id,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    result = service.list_assigned_and_available(
        scheme_type="UFLS", assigned_terminal_ids={circuit_terminals.pklg_terminal_id}
    )
    assert {c.id for c in result.assigned} == {assigned_functionality.id}
    assert {c.id for c in result.available} == {available_functionality.id}


# --- List/filter (general registry view) ---------------------------------------------


def test_list_functionality_filters_by_ufls_uvls_and_target_type(
    db_session: Session,
    circuit_terminals: CircuitTerminals,
    transformer_terminals: TransformerTerminals,
    actor_user_id: uuid.UUID,
) -> None:
    service = AutomaticLoadSheddingFunctionalityService(db_session)
    service.create(
        target_type="CIRCUIT_TERMINAL",
        circuit_terminal_id=circuit_terminals.pklg_terminal_id,
        transformer_terminal_id=None,
        ufls_function=True,
        uvls_function=False,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.create(
        target_type="TRANSFORMER_TERMINAL",
        circuit_terminal_id=None,
        transformer_terminal_id=transformer_terminals.hv_terminal_id,
        ufls_function=False,
        uvls_function=True,
        relay_make=None,
        relay_model=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    items, total = service.list_functionality(page=1, page_size=50, ufls_function=True)
    assert total == 1
    assert items[0].ufls_function is True

    items, total = service.list_functionality(page=1, page_size=50, status="AVAILABLE")
    assert total == 2

    items, total = service.list_functionality(
        page=1, page_size=50, target_type="TRANSFORMER_TERMINAL"
    )
    assert total == 1
    assert items[0].target_type == "TRANSFORMER_TERMINAL"
