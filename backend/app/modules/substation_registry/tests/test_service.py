"""Business rule tests for SubstationService — docs/architecture/
substation-registry.md §8 (Data Integrity Rules), §10 (CRUD Lifecycle).

Covers Phase 2's mandated test list (implementation-plan.md): mnemonic
uniqueness (case-insensitive), `substation_id` immutability, alias creation
on mnemonic change, geo coordinate pair validation, soft-delete-only
enforcement — plus the other business rules this checkpoint's
implementation enforces (name/PSS-E-bus uniqueness, reference-data
validation, status transition legality).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.modules.substation_registry.exceptions import (
    DuplicateMnemonicError,
    DuplicateNameError,
    DuplicatePsseBusNumberError,
    InvalidGeolocationPairError,
    InvalidStatusTransitionError,
    NotFoundError,
    ReferenceDataNotFoundError,
)
from app.modules.substation_registry.models import Substation
from app.modules.substation_registry.service import SubstationService
from app.modules.substation_registry.tests.conftest import ReferenceIds


def _create(
    service: SubstationService,
    ref: ReferenceIds,
    actor_user_id: uuid.UUID,
    *,
    mnemonic: str = "SUB1",
    official_name: str = "Substation One",
    status_code: str = "ACTIVE",
    psse_bus_number: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
):
    return service.create_substation(
        mnemonic=mnemonic,
        official_name=official_name,
        region_id=ref.region_id,
        state_id=ref.state_id,
        grid_owner_id=ref.grid_owner_id,
        operational_status_id=ref.status_id_by_code[status_code],
        psse_bus_number=psse_bus_number,
        latitude=latitude,
        longitude=longitude,
        commissioned_date=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )


# --- Mnemonic uniqueness (mandated) --------------------------------------------------
class TestMnemonicUniqueness:
    def test_duplicate_mnemonic_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        _create(service, reference_ids, actor_user_id, mnemonic="SUB1")
        db_session.commit()

        with pytest.raises(DuplicateMnemonicError):
            _create(service, reference_ids, actor_user_id, mnemonic="SUB1", official_name="Other")

    def test_duplicate_mnemonic_is_case_insensitive(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        _create(service, reference_ids, actor_user_id, mnemonic="Sub1")
        db_session.commit()

        with pytest.raises(DuplicateMnemonicError):
            _create(service, reference_ids, actor_user_id, mnemonic="SUB1", official_name="Other")

    def test_retired_mnemonic_cannot_be_reassigned_to_a_new_substation(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, mnemonic="OLD1")
        db_session.commit()
        service.update_substation(
            substation.substation_id, mnemonic="NEW1", actor_user_id=actor_user_id
        )
        db_session.commit()

        with pytest.raises(DuplicateMnemonicError):
            _create(service, reference_ids, actor_user_id, mnemonic="OLD1", official_name="Other")


# --- substation_id immutability (mandated) --------------------------------------------
class TestSubstationIdImmutability:
    def test_substation_id_is_unchanged_by_update(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()
        original_id = substation.substation_id

        service.update_substation(
            original_id, official_name="Renamed Substation", actor_user_id=actor_user_id
        )
        db_session.commit()

        reloaded = service.repo.get_by_id(original_id)
        assert reloaded is not None
        assert reloaded.substation_id == original_id

    def test_update_substation_schema_offers_no_substation_id_field(self) -> None:
        """The public update surface cannot even express changing the
        primary key — see app/modules/substation_registry/schemas.py's
        `SubstationUpdate`."""
        from app.modules.substation_registry.schemas import SubstationUpdate

        assert "substation_id" not in SubstationUpdate.model_fields


# --- Alias creation on mnemonic change (mandated) -----------------------------------
class TestAliasCreationOnMnemonicChange:
    def test_changing_mnemonic_creates_an_alias_for_the_old_value(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, mnemonic="OLD1")
        db_session.commit()

        service.update_substation(
            substation.substation_id, mnemonic="NEW1", actor_user_id=actor_user_id
        )
        db_session.commit()

        aliases = service.list_aliases(substation.substation_id)
        assert len(aliases) == 1
        assert aliases[0].alias_mnemonic == "OLD1"
        assert aliases[0].valid_to is not None

        reloaded = service.repo.get_by_id(substation.substation_id)
        assert reloaded is not None
        assert reloaded.mnemonic == "NEW1"

    def test_mnemonic_change_is_never_an_overwrite_in_place(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Two successive mnemonic changes leave two distinct alias rows —
        history is additive, not overwritten (substation-registry.md §8
        rule 1)."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, mnemonic="ORIG")
        db_session.commit()

        service.update_substation(
            substation.substation_id, mnemonic="SECOND", actor_user_id=actor_user_id
        )
        db_session.commit()
        service.update_substation(
            substation.substation_id, mnemonic="THIRD", actor_user_id=actor_user_id
        )
        db_session.commit()

        aliases = service.list_aliases(substation.substation_id)
        assert {a.alias_mnemonic for a in aliases} == {"ORIG", "SECOND"}

    def test_official_name_change_does_not_create_an_alias(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        service.update_substation(
            substation.substation_id, official_name="A New Name", actor_user_id=actor_user_id
        )
        db_session.commit()

        assert service.list_aliases(substation.substation_id) == []


# --- Geo coordinate pair validation (mandated) --------------------------------------
class TestGeolocationPairValidation:
    def test_latitude_without_longitude_on_create_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(InvalidGeolocationPairError):
            _create(service, reference_ids, actor_user_id, latitude=3.14)

    def test_longitude_without_latitude_on_create_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(InvalidGeolocationPairError):
            _create(service, reference_ids, actor_user_id, longitude=101.7)

    def test_both_coordinates_present_succeeds(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, latitude=3.14, longitude=101.7)
        assert substation.latitude is not None
        assert substation.longitude is not None

    def test_both_coordinates_null_succeeds(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        assert substation.latitude is None
        assert substation.longitude is None

    def test_update_setting_only_latitude_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(InvalidGeolocationPairError):
            service.update_substation(
                substation.substation_id, latitude=3.14, actor_user_id=actor_user_id
            )


# --- Name and PSS/E bus number uniqueness --------------------------------------------
class TestOtherUniquenessRules:
    def test_duplicate_official_name_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        _create(service, reference_ids, actor_user_id, official_name="Shared Name")
        db_session.commit()

        with pytest.raises(DuplicateNameError):
            _create(
                service,
                reference_ids,
                actor_user_id,
                mnemonic="OTHER",
                official_name="Shared Name",
            )

    def test_duplicate_psse_bus_number_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        _create(service, reference_ids, actor_user_id, psse_bus_number=101)
        db_session.commit()

        with pytest.raises(DuplicatePsseBusNumberError):
            _create(
                service,
                reference_ids,
                actor_user_id,
                mnemonic="OTHER",
                official_name="Other",
                psse_bus_number=101,
            )

    def test_multiple_substations_with_null_psse_bus_number_are_allowed(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        _create(service, reference_ids, actor_user_id, mnemonic="A1")
        db_session.commit()
        # Does not raise — NULL psse_bus_number is never considered a duplicate.
        _create(service, reference_ids, actor_user_id, mnemonic="A2", official_name="Second")


# --- Reference data validation --------------------------------------------------------
class TestReferenceDataValidation:
    def test_unknown_region_id_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(ReferenceDataNotFoundError):
            service.create_substation(
                mnemonic="SUB1",
                official_name="Substation One",
                region_id=99999,
                state_id=reference_ids.state_id,
                grid_owner_id=reference_ids.grid_owner_id,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                psse_bus_number=None,
                latitude=None,
                longitude=None,
                commissioned_date=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )

    def test_create_no_longer_accepts_voltage_level_id(self) -> None:
        """Deprecated (ADR-009) — voltage level is represented exclusively
        through SubstationVoltageYard now; Substation Create must not even
        be able to express it."""
        import inspect

        assert "voltage_level_id" not in inspect.signature(
            SubstationService.create_substation
        ).parameters


# --- Status transition legality (closed allow-list per ADR-005) -----------------------
class TestStatusTransitionLegality:
    def test_create_may_start_as_planned(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        assert substation.operational_status_id == reference_ids.status_id_by_code["PLANNED"]

    def test_create_may_start_as_active(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        assert substation.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_create_may_not_start_as_mothballed(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(InvalidStatusTransitionError):
            _create(service, reference_ids, actor_user_id, status_code="MOTHBALLED")

    def test_create_may_not_start_as_under_construction(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """§10's creation exception is unchanged by ADR-005 — still Planned
        or Active only, never Under Construction."""
        service = SubstationService(db_session)
        with pytest.raises(InvalidStatusTransitionError):
            _create(service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION")

    @staticmethod
    def _advance(
        service: SubstationService,
        substation: Substation,
        reference_ids: ReferenceIds,
        target_code: str,
        actor_user_id: uuid.UUID,
    ) -> Substation:
        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code[target_code],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        service.db.commit()
        return result

    # --- The seven legal edges (ADR-005) --------------------------------------------
    def test_planned_to_under_construction_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["UNDER_CONSTRUCTION"],
            change_reason="Construction started",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["UNDER_CONSTRUCTION"]

    def test_under_construction_to_active_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()
        self._advance(service, substation, reference_ids, "UNDER_CONSTRUCTION", actor_user_id)

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason="Commissioned",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_active_to_mothballed_and_back_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()

        service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["MOTHBALLED"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_active_to_decommissioned_directly_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """ADR-005: a substation may be decommissioned directly from Active
        — mothballing is not a mandatory precondition."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["DECOMMISSIONED"],
            change_reason="Structural failure",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["DECOMMISSIONED"]

    def test_mothballed_to_decommissioned_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()
        self._advance(service, substation, reference_ids, "MOTHBALLED", actor_user_id)

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["DECOMMISSIONED"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["DECOMMISSIONED"]

    def test_decommissioned_to_retired_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()
        self._advance(service, substation, reference_ids, "DECOMMISSIONED", actor_user_id)

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["RETIRED"],
            change_reason="Administrative closure",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["RETIRED"]

    def test_full_planned_to_retired_lifecycle_via_mothballed(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Exercises every edge in ADR-005's graph in a single, realistic
        end-to-end sequence."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()

        for code in ("UNDER_CONSTRUCTION", "ACTIVE", "MOTHBALLED", "DECOMMISSIONED", "RETIRED"):
            self._advance(service, substation, reference_ids, code, actor_user_id)

        reloaded = service.repo.get_by_id(substation.substation_id)
        assert reloaded is not None
        assert reloaded.operational_status_id == reference_ids.status_id_by_code["RETIRED"]

    # --- Rejected transitions --------------------------------------------------------
    def test_planned_to_active_directly_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """ADR-005: Planned must pass through Under Construction — direct
        Planned -> Active is no longer legal (a behavioural change from
        Phase 2's original interim implementation)."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_planned_to_decommissioned_directly_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["DECOMMISSIONED"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_active_to_under_construction_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["UNDER_CONSTRUCTION"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_under_construction_to_planned_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()
        self._advance(service, substation, reference_ids, "UNDER_CONSTRUCTION", actor_user_id)

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["PLANNED"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_under_construction_to_mothballed_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()
        self._advance(service, substation, reference_ids, "UNDER_CONSTRUCTION", actor_user_id)

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["MOTHBALLED"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_retired_is_terminal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()
        for code in ("MOTHBALLED", "DECOMMISSIONED", "RETIRED"):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code[code],
                change_reason=None,
                actor_user_id=actor_user_id,
            )
            db_session.commit()

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_setting_the_same_status_again_is_an_idempotent_no_op(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()

        service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 0


# --- Audit logging (field-level) -----------------------------------------------------
class TestAuditLogging:
    def test_update_writes_one_audit_row_per_changed_field(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        service.update_substation(
            substation.substation_id,
            official_name="Renamed",
            remarks="Now with remarks",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 2
        field_names = {e.field_name for e in entries}
        assert field_names == {"official_name", "remarks"}

    def test_create_writes_no_audit_row(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Creation accountability is captured by created_by_user_id/
        created_at directly on the row — see service.py's docstring."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        _entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 0

    def test_status_change_writes_an_audit_row_with_the_change_reason(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="PLANNED")
        db_session.commit()

        service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["UNDER_CONSTRUCTION"],
            change_reason="Construction started ahead of schedule",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "operational_status_id"
        assert entries[0].old_value == "PLANNED"
        assert entries[0].new_value == "UNDER_CONSTRUCTION"
        assert entries[0].change_reason == "Construction started ahead of schedule"


# --- Soft-delete-only enforcement (mandated) ------------------------------------------
class TestSoftDeleteOnlyEnforcement:
    def test_repository_exposes_no_delete_method(self) -> None:
        from app.modules.substation_registry.repository import SubstationRepository

        assert not hasattr(SubstationRepository, "delete")
        assert not hasattr(SubstationRepository, "delete_substation")
        assert not hasattr(SubstationRepository, "hard_delete")

    def test_service_exposes_no_delete_method(self) -> None:
        assert not hasattr(SubstationService, "delete_substation")
        assert not hasattr(SubstationService, "delete")
        assert not hasattr(SubstationService, "hard_delete")

    def test_router_registers_no_delete_endpoint(self) -> None:
        from app.modules.substation_registry.router import router

        assert not any("DELETE" in (route.methods or set()) for route in router.routes)

    def test_lifecycle_status_change_is_the_only_way_to_retire_a_substation(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()

        for code in ("MOTHBALLED", "DECOMMISSIONED", "RETIRED"):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code[code],
                change_reason=None,
                actor_user_id=actor_user_id,
            )
            db_session.commit()

        # The row still exists and is still readable — "retired" is a
        # status, never a deleted row.
        assert service.repo.get_by_id(substation.substation_id) is not None


# --- Not-found guards ------------------------------------------------------------------
class TestNotFoundGuards:
    def test_update_unknown_substation_raises_not_found(
        self, db_session: Session, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(NotFoundError):
            service.update_substation(
                uuid.uuid4(), official_name="Doesn't matter", actor_user_id=actor_user_id
            )

    def test_change_status_on_unknown_substation_raises_not_found(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(NotFoundError):
            service.change_status(
                uuid.uuid4(),
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_get_unknown_substation_returns_none(self, db_session: Session) -> None:
        service = SubstationService(db_session)
        assert service.get_substation(uuid.uuid4()) is None
