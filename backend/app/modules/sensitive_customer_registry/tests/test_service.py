"""Service-layer tests for the Sensitive Customer Registry — business
rules, validation, lifecycle, audit, and the stable read/batch-lookup
contracts (sensitive-customer-registry-module.md;
sensitive-customer-registry-implementation-spec.md §15).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.sensitive_customer_registry.exceptions import (
    FacilityEnteredInErrorImmutableError,
    FacilitySectorInactiveError,
    InvalidLifecycleTransitionError,
    LifecycleReasonRequiredError,
    ReassignmentReasonRequiredError,
    ReferenceDataNotSeededError,
    SensitivityClassificationInactiveError,
    TransformerTerminalNotFoundError,
)
from app.modules.sensitive_customer_registry.service import SensitiveCustomerRegistryService

# --- Create -------------------------------------------------------------------


def test_create_facility_without_terminal(db_session: Session, scr_reference_ids, actor_user_id):
    """An `ACTIVE` facility with no associated terminals (resolution
    `NOT_ASSIGNED`) is a deliberate, explicitly-authorised normal state, not
    an edge case to be prevented — module doc §7/§9 rule 5 and ADR-012
    decision 2 both state "a facility may be registered as sensitive before
    its supply point is confirmed." This test pins that behaviour
    explicitly so it is never mistaken for a defect in a future review."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert facility.lifecycle_status == "ACTIVE"

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.lifecycle_status == "ACTIVE"
    assert detail.transformer_terminals == []
    assert detail.transformer_terminal_resolution == "NOT_ASSIGNED"


def test_create_facility_with_terminal(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert [t.transformer_terminal_id for t in detail.transformer_terminals] == [
        transformer_terminals.hv_terminal_id
    ]


def test_create_facility_with_multiple_terminals(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    second_transformer_terminals,
):
    """ADR-013 — a facility may currently be associated with more than one
    Transformer Terminal (e.g. a dual-fed facility)."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[
            transformer_terminals.hv_terminal_id,
            second_transformer_terminals.hv_terminal_id,
        ],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    associated_ids = {t.transformer_terminal_id for t in detail.transformer_terminals}
    assert associated_ids == {
        transformer_terminals.hv_terminal_id,
        second_transformer_terminals.hv_terminal_id,
    }
    assert all(t.resolution == "RESOLVED" for t in detail.transformer_terminals)
    assert detail.transformer_terminal_resolution == "RESOLVED"


def test_create_facility_dedupes_duplicate_terminal_ids(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    """A duplicate id in the request is silently collapsed, not rejected as
    invalid — the associated terminals are an unordered set (ADR-013)."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[
            transformer_terminals.hv_terminal_id,
            transformer_terminals.hv_terminal_id,
        ],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert len(detail.transformer_terminals) == 1


def test_create_facility_against_unknown_terminal_rejected(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    with pytest.raises(TransformerTerminalNotFoundError):
        service.create_facility(
            name="Hospital Kuala Lumpur",
            facility_sector_id=scr_reference_ids.healthcare_sector_id,
            sensitivity_classification_id=scr_reference_ids.high_classification_id,
            transformer_terminal_ids=[uuid.uuid4()],
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_create_facility_against_inactive_sector_rejected(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    service.update_facility_sector(
        scr_reference_ids.transport_sector_id, is_active=False, actor_user_id=actor_user_id
    )
    db_session.commit()

    with pytest.raises(FacilitySectorInactiveError):
        service.create_facility(
            name="Some Airport",
            facility_sector_id=scr_reference_ids.transport_sector_id,
            sensitivity_classification_id=scr_reference_ids.high_classification_id,
            transformer_terminal_ids=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_create_facility_against_inactive_classification_rejected(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    service.update_sensitivity_classification(
        scr_reference_ids.medium_classification_id, is_active=False, actor_user_id=actor_user_id
    )
    db_session.commit()

    with pytest.raises(SensitivityClassificationInactiveError):
        service.create_facility(
            name="Some Facility",
            facility_sector_id=scr_reference_ids.healthcare_sector_id,
            sensitivity_classification_id=scr_reference_ids.medium_classification_id,
            transformer_terminal_ids=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_create_facility_without_seeded_reference_data_raises(db_session: Session, actor_user_id):
    """No `scr_reference_ids` fixture — reference tables are genuinely
    empty (implementation spec §13's fail-loud safeguard)."""
    service = SensitiveCustomerRegistryService(db_session)
    with pytest.raises(ReferenceDataNotSeededError):
        service.create_facility(
            name="Hospital Kuala Lumpur",
            facility_sector_id=1,
            sensitivity_classification_id=1,
            transformer_terminal_ids=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )


def test_multiple_facilities_may_share_one_terminal(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    """The deliberate inverse of ALSF's own per-terminal uniqueness rule
    (module document §7, §9 rule 3)."""
    service = SensitiveCustomerRegistryService(db_session)
    first = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    second = service.create_facility(
        name="Government Building",
        facility_sector_id=scr_reference_ids.transport_sector_id,
        sensitivity_classification_id=scr_reference_ids.medium_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert first.id != second.id
    first_detail = service.get_facility_detail(first.id)
    second_detail = service.get_facility_detail(second.id)
    assert first_detail is not None and second_detail is not None
    assert [t.transformer_terminal_id for t in first_detail.transformer_terminals] == [
        transformer_terminals.hv_terminal_id
    ]
    assert [t.transformer_terminal_id for t in second_detail.transformer_terminals] == [
        transformer_terminals.hv_terminal_id
    ]


def test_facility_names_are_not_required_to_be_unique(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    first = service.create_facility(
        name="Same Name Clinic",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    second = service.create_facility(
        name="Same Name Clinic",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.medium_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert first.id != second.id
    assert first.name == second.name


# --- Update metadata / reassignment (Correction 5) ---------------------------


def test_update_metadata_name_change_audited(db_session: Session, scr_reference_ids, actor_user_id):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Old Name",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.update_metadata(facility.id, name="New Name", actor_user_id=actor_user_id)
    db_session.commit()

    entries, total = service.list_facility_audit_log(facility.id, page=1, page_size=50)
    assert total == 2  # creation + name change
    assert any(e.field_name == "name" and e.new_value == "New Name" for e in entries)


def test_audit_log_ordering_is_deterministic_for_same_timestamp_rows(
    db_session: Session, scr_reference_ids, actor_user_id
):
    """A single `update_metadata` call auditing multiple changed fields at
    once writes several rows within one transaction — they can share the
    exact same `changed_at` value. Ordering must still be deterministic
    (most-recent-`log_id`-first among ties), not left to chance."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Old Name",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks="Old remarks",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.update_metadata(
        facility.id, name="New Name", remarks="New remarks", actor_user_id=actor_user_id
    )
    db_session.commit()

    entries, total = service.list_facility_audit_log(facility.id, page=1, page_size=50)
    assert total == 3  # creation + name change + remarks change
    log_ids = [e.log_id for e in entries]
    assert log_ids == sorted(log_ids, reverse=True), "audit entries must be in log_id-desc order"


# --- Terminal associations (ADR-013) -------------------------------------------


def test_set_terminal_associations_without_reason_rejected_when_changing(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(ReassignmentReasonRequiredError):
        service.set_terminal_associations(
            facility.id,
            transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
            change_reason=None,
            actor_user_id=actor_user_id,
        )


def test_set_terminal_associations_noop_does_not_require_reason(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    """A call whose target set equals the current set makes no change and
    is not treated as a reassignment — no reason is required."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.set_terminal_associations(
        facility.id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        change_reason=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    entries, total = service.list_facility_audit_log(facility.id, page=1, page_size=50)
    assert total == 1  # creation only — the no-op produced no audit row


def test_set_terminal_associations_add_and_remove_in_one_call_audits_each_change(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    second_transformer_terminals,
):
    """ADR-013 decision 3 — a multi-terminal edit is one API/service call
    that internally diffs the target set and writes one audit row per
    actual addition or removal, never one opaque bulk event."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.set_terminal_associations(
        facility.id,
        transformer_terminal_ids=[second_transformer_terminals.hv_terminal_id],
        change_reason="Supply point corrected after site survey",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert [t.transformer_terminal_id for t in detail.transformer_terminals] == [
        second_transformer_terminals.hv_terminal_id
    ]

    entries, total = service.list_facility_audit_log(facility.id, page=1, page_size=50)
    assert total == 3  # creation + one removal row + one addition row
    changes = [e for e in entries if e.field_name == "transformer_terminal_id"]
    assert len(changes) == 2
    removal = next(e for e in changes if e.old_value == str(transformer_terminals.hv_terminal_id))
    assert removal.new_value is None
    assert removal.change_reason == "Supply point corrected after site survey"
    addition = next(
        e for e in changes if e.new_value == str(second_transformer_terminals.hv_terminal_id)
    )
    assert addition.old_value is None
    assert addition.change_reason == "Supply point corrected after site survey"
    assert addition.changed_by is not None
    assert addition.changed_by.user_id == actor_user_id


def test_set_terminal_associations_add_only(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    second_transformer_terminals,
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.set_terminal_associations(
        facility.id,
        transformer_terminal_ids=[
            transformer_terminals.hv_terminal_id,
            second_transformer_terminals.hv_terminal_id,
        ],
        change_reason="A second supply point was confirmed",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    associated_ids = {t.transformer_terminal_id for t in detail.transformer_terminals}
    assert associated_ids == {
        transformer_terminals.hv_terminal_id,
        second_transformer_terminals.hv_terminal_id,
    }


def test_set_terminal_associations_remove_only_to_empty(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.set_terminal_associations(
        facility.id,
        transformer_terminal_ids=[],
        change_reason="Supply point decommissioned",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.transformer_terminals == []
    assert detail.transformer_terminal_resolution == "NOT_ASSIGNED"


def test_set_terminal_associations_dedupes_duplicate_ids_in_request(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.set_terminal_associations(
        facility.id,
        transformer_terminal_ids=[
            transformer_terminals.hv_terminal_id,
            transformer_terminals.hv_terminal_id,
        ],
        change_reason="Supply point confirmed",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert len(detail.transformer_terminals) == 1


def test_set_terminal_associations_to_unknown_terminal_rejected(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    with pytest.raises(TransformerTerminalNotFoundError):
        service.set_terminal_associations(
            facility.id,
            transformer_terminal_ids=[transformer_terminals.hv_terminal_id, uuid.uuid4()],
            change_reason="Attempted correction",
            actor_user_id=actor_user_id,
        )


def test_set_terminal_associations_on_entered_in_error_facility_rejected(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    service.mark_entered_in_error(
        facility.id, change_reason="Duplicate record", actor_user_id=actor_user_id
    )

    with pytest.raises(FacilityEnteredInErrorImmutableError):
        service.set_terminal_associations(
            facility.id,
            transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
            change_reason="Attempted correction",
            actor_user_id=actor_user_id,
        )


# --- Lifecycle (module document §8) -------------------------------------------


def _create(service, scr_reference_ids, actor_user_id):
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    return facility


def test_archive_requires_reason(db_session: Session, scr_reference_ids, actor_user_id):
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()
    with pytest.raises(LifecycleReasonRequiredError):
        service.archive(facility.id, change_reason=None, actor_user_id=actor_user_id)


def test_archive_then_reactivate_round_trip(db_session: Session, scr_reference_ids, actor_user_id):
    """`_create` builds a facility with no terminal — this round trip also
    confirms lifecycle transitions never touch `transformer_terminal_id`
    (archive/reactivate are lifecycle-only operations, module doc §8), so a
    `NOT_ASSIGNED` facility reactivates back to `NOT_ASSIGNED`, never
    silently gaining or losing a terminal reference."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()

    archived = service.archive(
        facility.id, change_reason="Facility closed", actor_user_id=actor_user_id
    )
    assert archived.lifecycle_status == "ARCHIVED"

    reactivated = service.reactivate(
        facility.id, change_reason="Facility reopened", actor_user_id=actor_user_id
    )
    assert reactivated.lifecycle_status == "ACTIVE"

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.transformer_terminals == []
    assert detail.transformer_terminal_resolution == "NOT_ASSIGNED"


def test_archive_then_reactivate_preserves_assigned_terminal(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    """The inverse of the test above — a facility that *does* have a
    terminal must keep it, unchanged, through an archive/reactivate cycle."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.archive(facility.id, change_reason="Facility closed", actor_user_id=actor_user_id)
    service.reactivate(facility.id, change_reason="Facility reopened", actor_user_id=actor_user_id)

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert [t.transformer_terminal_id for t in detail.transformer_terminals] == [
        transformer_terminals.hv_terminal_id
    ]
    assert detail.transformer_terminal_resolution == "RESOLVED"


def test_active_to_entered_in_error(db_session: Session, scr_reference_ids, actor_user_id):
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()

    result = service.mark_entered_in_error(
        facility.id, change_reason="Duplicate record", actor_user_id=actor_user_id
    )
    assert result.lifecycle_status == "ENTERED_IN_ERROR"


def test_archived_to_entered_in_error(db_session: Session, scr_reference_ids, actor_user_id):
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()
    service.archive(facility.id, change_reason="Closed", actor_user_id=actor_user_id)

    result = service.mark_entered_in_error(
        facility.id, change_reason="Should never have been created", actor_user_id=actor_user_id
    )
    assert result.lifecycle_status == "ENTERED_IN_ERROR"


@pytest.mark.parametrize("action", ["archive", "reactivate", "mark_entered_in_error"])
def test_entered_in_error_is_terminal_no_transition_out(
    db_session: Session, scr_reference_ids, actor_user_id, action
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()
    service.mark_entered_in_error(
        facility.id, change_reason="Duplicate record", actor_user_id=actor_user_id
    )

    with pytest.raises(InvalidLifecycleTransitionError):
        getattr(service, action)(
            facility.id, change_reason="Attempted transition", actor_user_id=actor_user_id
        )


def test_entered_in_error_facility_immutable_to_metadata_edit(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()
    service.mark_entered_in_error(
        facility.id, change_reason="Duplicate record", actor_user_id=actor_user_id
    )

    with pytest.raises(FacilityEnteredInErrorImmutableError):
        service.update_metadata(facility.id, name="New Name", actor_user_id=actor_user_id)


# --- Read: terminal resolution (Correction 4) ---------------------------------


def test_facility_detail_not_assigned_when_no_terminal(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = _create(service, scr_reference_ids, actor_user_id)
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.transformer_terminal_resolution == "NOT_ASSIGNED"
    assert detail.transformer_terminals == []


def test_facility_detail_resolved_with_real_terminal(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.transformer_terminal_resolution == "RESOLVED"
    assert len(detail.transformer_terminals) == 1
    association = detail.transformer_terminals[0]
    assert association.resolution == "RESOLVED"
    assert association.substation_mnemonic == "PKLG"
    assert association.bay_label is not None and association.bay_label.startswith("Transformer ")


def test_facility_never_omitted_from_list_when_terminal_unresolved(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    monkeypatch: pytest.MonkeyPatch,
):
    """Correction 4 — a facility whose terminal cannot currently be
    resolved is still returned by list_facilities/get_facility_detail,
    never silently dropped."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    # Simulate Equipment Registry being unable to resolve this terminal
    # right now (e.g. a stale reference) without violating referential
    # integrity by pointing at a genuinely nonexistent row.
    monkeypatch.setattr(
        service.equipment_registry, "get_transformer_terminal_identity", lambda _id: None
    )

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.transformer_terminal_resolution == "UNRESOLVED"
    assert detail.transformer_terminals[0].resolution == "UNRESOLVED"
    assert detail.lifecycle_status == "ACTIVE"

    items, total = service.list_facilities(page=1, page_size=50)
    assert total == 1
    assert items[0].id == facility.id
    assert items[0].transformer_terminal_resolution == "UNRESOLVED"


def test_facility_with_multiple_terminals_aggregate_unresolved_when_any_association_unresolved(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    second_transformer_terminals,
    monkeypatch: pytest.MonkeyPatch,
):
    """ADR-013 decision 4 — the facility-level aggregate is UNRESOLVED as
    soon as one association is unresolved, but the full per-association
    detail is always exposed: the still-resolved association must not be
    silently collapsed away by the aggregate."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[
            transformer_terminals.hv_terminal_id,
            second_transformer_terminals.hv_terminal_id,
        ],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    original_get_identity = service.equipment_registry.get_transformer_terminal_identity

    def _only_first_resolves(terminal_id):
        if terminal_id == second_transformer_terminals.hv_terminal_id:
            return None
        return original_get_identity(terminal_id)

    monkeypatch.setattr(
        service.equipment_registry, "get_transformer_terminal_identity", _only_first_resolves
    )

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.transformer_terminal_resolution == "UNRESOLVED"
    assert len(detail.transformer_terminals) == 2
    resolutions = {t.transformer_terminal_id: t.resolution for t in detail.transformer_terminals}
    assert resolutions[transformer_terminals.hv_terminal_id] == "RESOLVED"
    assert resolutions[second_transformer_terminals.hv_terminal_id] == "UNRESOLVED"


# --- Batch lookup (implementation spec §9) ------------------------------------


def test_batch_lookup_completeness(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    second_transformer_terminals,
):
    service = SensitiveCustomerRegistryService(db_session)
    service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.create_facility(
        name="Government Office",
        facility_sector_id=scr_reference_ids.transport_sector_id,
        sensitivity_classification_id=scr_reference_ids.medium_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    requested = {
        transformer_terminals.hv_terminal_id,
        second_transformer_terminals.hv_terminal_id,  # no facilities
        uuid.uuid4(),  # unknown terminal id entirely
    }
    results = service.get_sensitive_facilities_for_transformer_terminals(requested)

    assert set(results.keys()) == requested
    assert len(results[transformer_terminals.hv_terminal_id]) == 2
    assert results[second_transformer_terminals.hv_terminal_id] == []


def test_batch_lookup_matches_facility_under_every_associated_terminal_key(
    db_session: Session,
    scr_reference_ids,
    actor_user_id,
    transformer_terminals,
    second_transformer_terminals,
):
    """ADR-013 decision 5 — "any associated terminal matches": a facility
    associated with both terminal A and terminal B appears under both A's
    and B's key when both are requested in the same batch."""
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[
            transformer_terminals.hv_terminal_id,
            second_transformer_terminals.hv_terminal_id,
        ],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    requested = {transformer_terminals.hv_terminal_id, second_transformer_terminals.hv_terminal_id}
    results = service.get_sensitive_facilities_for_transformer_terminals(requested)

    assert [f.id for f in results[transformer_terminals.hv_terminal_id]] == [facility.id]
    assert [f.id for f in results[second_transformer_terminals.hv_terminal_id]] == [facility.id]


def test_batch_lookup_empty_input(db_session: Session, actor_user_id):
    service = SensitiveCustomerRegistryService(db_session)
    assert service.get_sensitive_facilities_for_transformer_terminals(set()) == {}


def test_has_sensitive_facility(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    assert service.has_sensitive_facility(transformer_terminals.hv_terminal_id) is False

    service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    assert service.has_sensitive_facility(transformer_terminals.hv_terminal_id) is True


def test_archived_facility_excluded_from_active_reads(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    service.archive(facility.id, change_reason="Closed", actor_user_id=actor_user_id)

    assert service.has_sensitive_facility(transformer_terminals.hv_terminal_id) is False
    assert (
        service.get_sensitive_facilities_for_transformer_terminal(
            transformer_terminals.hv_terminal_id
        )
        == []
    )


# --- Reference-data administration --------------------------------------------


def test_facility_sector_seed_idempotent(db_session: Session):
    from app.modules.sensitive_customer_registry.seed import run_seed

    first = run_seed(db_session)
    second = run_seed(db_session)
    assert first["facility_sector"] == 8
    assert first["sensitivity_classification"] == 3
    assert second["facility_sector"] == 0
    assert second["sensitivity_classification"] == 0


def test_seed_created_rows_have_null_actor_but_service_created_rows_always_have_a_real_actor(
    db_session: Session, actor_user_id
):
    """The null-creator/modifier exception is limited to the unattended
    seed script — every row created or edited through the service layer
    (the only path the API can reach) always records a real, authenticated
    actor. This pins the exact boundary of the exception so it can never
    silently widen to permit an unauthenticated mutation."""
    from app.modules.sensitive_customer_registry.models import FacilitySector
    from app.modules.sensitive_customer_registry.seed import run_seed

    run_seed(db_session)
    db_session.commit()

    seeded = db_session.query(FacilitySector).filter_by(code="HEALTHCARE").one()
    assert seeded.created_by_user_id is None
    assert seeded.updated_by_user_id is None

    service = SensitiveCustomerRegistryService(db_session)
    created = service.create_facility_sector(
        code="EDUCATION",
        label="Education",
        sort_order=9,
        description=None,
        actor_user_id=actor_user_id,
    )
    assert created.created_by_user_id == actor_user_id
    assert created.updated_by_user_id == actor_user_id

    service.update_facility_sector(
        seeded.id, label="Healthcare & Medical", actor_user_id=actor_user_id
    )
    db_session.commit()
    reloaded = db_session.query(FacilitySector).filter_by(code="HEALTHCARE").one()
    # created_by remains None (this row was never created through the
    # service layer), but updated_by now reflects the real actor who
    # edited it — the null-actor exception never retroactively applies to
    # a genuine administrator mutation.
    assert reloaded.created_by_user_id is None
    assert reloaded.updated_by_user_id == actor_user_id


def test_facility_sector_code_immutable_after_creation(
    db_session: Session, scr_reference_ids, actor_user_id
):
    """`FacilitySectorUpdate` has no `code` field at the schema level — this
    test confirms the service method itself has no way to change it."""
    service = SensitiveCustomerRegistryService(db_session)
    import inspect

    assert "code" not in inspect.signature(service.update_facility_sector).parameters


def test_rename_facility_sector_label_preserves_fk_and_audits_change(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.update_facility_sector(
        scr_reference_ids.healthcare_sector_id,
        label="Healthcare & Medical Facilities",
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.facility_sector.label == "Healthcare & Medical Facilities"
    assert detail.facility_sector.id == scr_reference_ids.healthcare_sector_id


def test_deactivating_sector_in_use_does_not_error_or_affect_existing_facility(
    db_session: Session, scr_reference_ids, actor_user_id
):
    service = SensitiveCustomerRegistryService(db_session)
    facility = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()

    service.update_facility_sector(
        scr_reference_ids.healthcare_sector_id, is_active=False, actor_user_id=actor_user_id
    )
    db_session.commit()

    detail = service.get_facility_detail(facility.id)
    assert detail is not None
    assert detail.facility_sector.id == scr_reference_ids.healthcare_sector_id
    assert detail.facility_sector.is_active is False


# --- Dashboard summary (implementation spec §11) ------------------------------


def test_summary_counts(
    db_session: Session, scr_reference_ids, actor_user_id, transformer_terminals
):
    service = SensitiveCustomerRegistryService(db_session)
    a = service.create_facility(
        name="Hospital Kuala Lumpur",
        facility_sector_id=scr_reference_ids.healthcare_sector_id,
        sensitivity_classification_id=scr_reference_ids.high_classification_id,
        transformer_terminal_ids=[transformer_terminals.hv_terminal_id],
        remarks=None,
        actor_user_id=actor_user_id,
    )
    service.create_facility(
        name="Government Office",
        facility_sector_id=scr_reference_ids.transport_sector_id,
        sensitivity_classification_id=scr_reference_ids.medium_classification_id,
        transformer_terminal_ids=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    service.archive(a.id, change_reason="Closed", actor_user_id=actor_user_id)

    counts = service.get_summary_counts()
    assert counts.active_count == 1
    assert counts.archived_count == 1
    assert counts.entered_in_error_count == 0
    assert counts.by_sector.get("TRANSPORT") == 1


# --- Architectural test --------------------------------------------------------


def test_module_never_imports_scheme_or_sibling_registry_modules():
    """No `sensitive_customer_registry` source file actually **imports**
    (not merely mentions in a docstring/comment) Network Model, ALSF,
    Critical Infrastructure, or any scheme module's `repository.py`/
    `service.py`/`models.py` (ADR-012 Service Interface Expectations;
    implementation spec §9, §16). Parses real `import`/`from ... import`
    statements via the `ast` module rather than a substring search, so a
    prose mention of another module's name in a comment (e.g. "mirrors
    ALSF's own bootstrap.py pattern") never produces a false positive."""
    import ast
    import pathlib

    forbidden_module_prefixes = (
        "app.modules.network_model",
        "app.modules.automatic_load_shedding_functionality",
        "app.modules.critical_infrastructure",
        "app.modules.ufls",
        "app.modules.uvls",
        "app.modules.emls",
    )
    module_dir = pathlib.Path(__file__).resolve().parent.parent
    for py_file in module_dir.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            imported_names: list[str] = []
            if isinstance(node, ast.Import):
                imported_names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_names = [node.module]
            for name in imported_names:
                for forbidden in forbidden_module_prefixes:
                    assert not name.startswith(forbidden), (
                        f"{py_file.name} imports '{name}' (forbidden: '{forbidden}')"
                    )


# --- Standalone entrypoint regression (UAT-preparation finding) --------------


def test_seed_runs_successfully_as_a_true_standalone_process(tmp_path):
    """Regression test for a real defect found during UAT preparation:
    `python -m app.modules.sensitive_customer_registry.seed`, run as a
    genuinely separate process (fresh Python import state, exactly how an
    operator actually invokes it — README.md's "Seeding and Bootstrapping"
    section), failed with `sqlalchemy.exc.NoReferencedTableError` because
    nothing in `seed.py`'s own import chain registered IAM's `user` table
    in `Base.metadata`, which `FacilitySector`/`SensitivityClassification`'s
    `created_by_user_id`/`updated_by_user_id` FKs need at flush time.

    This could never be caught by a normal in-process pytest call to
    `run_seed(db_session)` — the root `conftest.py` already imports
    `app.main` (and therefore every module's models) before any test body
    runs, masking the exact gap a real standalone invocation hits. A real
    subprocess, with its own fresh interpreter, is the only way to
    reproduce and pin this fix."""
    import os
    import pathlib
    import subprocess
    import sys

    from sqlalchemy import create_engine, text

    from app.db.base import Base
    from app.modules.equipment_registry import models as equipment_registry_models  # noqa: F401
    from app.modules.iam import models as iam_models  # noqa: F401
    from app.modules.sensitive_customer_registry import (  # noqa: F401
        models as scr_models,
    )
    from app.modules.substation_registry import models as substation_registry_models  # noqa: F401
    from app.reference_data import models as reference_data_models  # noqa: F401

    db_path = tmp_path / "seed_standalone_test.db"
    database_url = f"sqlite:///{db_path}"

    # Build the schema in this process (full metadata already registered
    # here) — the bug under test is specifically about the *subprocess's*
    # own fresh import state, not schema creation.
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()

    backend_dir = pathlib.Path(__file__).resolve().parents[4]
    result = subprocess.run(
        [sys.executable, "-m", "app.modules.sensitive_customer_registry.seed"],
        env={**os.environ, "DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        cwd=str(backend_dir),
    )
    assert result.returncode == 0, (
        f"seed.py failed as a standalone process:\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )

    verify_engine = create_engine(database_url)
    with verify_engine.connect() as conn:
        sector_count = conn.execute(text("SELECT COUNT(*) FROM facility_sector")).scalar_one()
        classification_count = conn.execute(
            text("SELECT COUNT(*) FROM sensitivity_classification")
        ).scalar_one()
    verify_engine.dispose()
    assert sector_count == 8
    assert classification_count == 3
