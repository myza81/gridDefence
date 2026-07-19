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
    MnemonicReservedByHistoricalSubstationError,
    NotFoundError,
    ReferenceDataNotFoundError,
)
from app.modules.substation_registry.models import Substation
from app.modules.substation_registry.service import SubstationService
from app.modules.substation_registry.tests.conftest import ReferenceIds

# Sentinel distinguishing "_create caller did not mention state" (use the
# fixture's state, preserving every pre-existing test's behaviour) from an
# explicit `state_id=None` (create a substation with no State — ADR-026).
_STATE_UNSET = object()


def _create(
    service: SubstationService,
    ref: ReferenceIds,
    actor_user_id: uuid.UUID,
    *,
    mnemonic: str = "SUB1",
    official_name: str = "Substation One",
    status_code: str = "ACTIVE",
    gm_zone_id: int | None = None,
    state_id: object = _STATE_UNSET,
    psse_bus_number: int | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
):
    # gm_zone_id is unconditionally required (like region_id/grid_owner_id)
    # — defaults to `ref.gm_zone_id` unless a caller is specifically
    # exercising an unknown/invalid id.
    resolved_gm_zone_id = ref.gm_zone_id if gm_zone_id is None else gm_zone_id
    # State is optional (ADR-026): default to the fixture's state (so every
    # pre-existing test is unchanged), but let a caller pass state_id=None
    # to create a stateless substation.
    resolved_state_id = ref.state_id if state_id is _STATE_UNSET else state_id
    return service.create_substation(
        mnemonic=mnemonic,
        official_name=official_name,
        region_id=ref.region_id,
        gm_zone_id=resolved_gm_zone_id,
        state_id=resolved_state_id,
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

        with pytest.raises(MnemonicReservedByHistoricalSubstationError):
            _create(service, reference_ids, actor_user_id, mnemonic="OLD1", official_name="Other")


# --- Mnemonic ownership across rename (UAT regression) ---------------------------------
class TestMnemonicOwnershipAcrossRename:
    """UAT found that SIDS -> SIDST -> SIDS on the *same* substation was
    incorrectly rejected: `_check_mnemonic_available` checked whether
    "SIDS" existed anywhere in `substation_alias` without checking *whose*
    alias it was, so a substation always collided with its own retired
    mnemonic. Fixed by having the repository return the alias's owning
    `substation_id` so the service can allow reuse by that same substation
    while still rejecting reuse by a different one."""

    def test_same_substation_can_reactivate_its_own_historical_mnemonic(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, mnemonic="SIDS")
        db_session.commit()

        service.update_substation(
            substation.substation_id, mnemonic="SIDST", actor_user_id=actor_user_id
        )
        db_session.commit()

        # Renaming back to its own retired mnemonic must be allowed.
        updated = service.update_substation(
            substation.substation_id, mnemonic="SIDS", actor_user_id=actor_user_id
        )
        db_session.commit()

        assert updated.mnemonic == "SIDS"

    def test_current_mnemonic_of_another_substation_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        _create(
            service, reference_ids, actor_user_id, mnemonic="SIDS", official_name="Substation A"
        )
        db_session.commit()

        with pytest.raises(DuplicateMnemonicError):
            _create(
                service,
                reference_ids,
                actor_user_id,
                mnemonic="SIDS",
                official_name="Substation B",
            )

    def test_historical_mnemonic_of_another_substation_is_rejected_on_create(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation_a = _create(
            service, reference_ids, actor_user_id, mnemonic="SIDS", official_name="Substation A"
        )
        db_session.commit()
        service.update_substation(
            substation_a.substation_id, mnemonic="SIDST", actor_user_id=actor_user_id
        )
        db_session.commit()

        with pytest.raises(MnemonicReservedByHistoricalSubstationError):
            _create(
                service,
                reference_ids,
                actor_user_id,
                mnemonic="SIDS",
                official_name="Substation B",
            )

    def test_historical_mnemonic_of_another_substation_is_rejected_on_update(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation_a = _create(
            service, reference_ids, actor_user_id, mnemonic="SIDS", official_name="Substation A"
        )
        db_session.commit()
        service.update_substation(
            substation_a.substation_id, mnemonic="SIDST", actor_user_id=actor_user_id
        )
        substation_b = _create(
            service, reference_ids, actor_user_id, mnemonic="OTHR", official_name="Substation B"
        )
        db_session.commit()

        with pytest.raises(MnemonicReservedByHistoricalSubstationError):
            service.update_substation(
                substation_b.substation_id, mnemonic="SIDS", actor_user_id=actor_user_id
            )


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

    def test_same_substation_can_rename_back_to_its_own_former_name(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Unlike mnemonic, official_name has no alias/reservation table
        (substation-registry.md §8 rule 1 singles out mnemonic only), so
        this already worked correctly before the mnemonic fix — recorded
        here as a regression test so the two rules' parity is verified,
        not merely assumed."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, official_name="Original Name")
        db_session.commit()

        service.update_substation(
            substation.substation_id, official_name="Renamed", actor_user_id=actor_user_id
        )
        db_session.commit()

        updated = service.update_substation(
            substation.substation_id, official_name="Original Name", actor_user_id=actor_user_id
        )
        db_session.commit()

        assert updated.official_name == "Original Name"

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
                gm_zone_id=reference_ids.gm_zone_id,
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

        assert (
            "voltage_level_id"
            not in inspect.signature(SubstationService.create_substation).parameters
        )

    def test_unknown_gm_zone_id_raises(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(ReferenceDataNotFoundError):
            _create(service, reference_ids, actor_user_id, gm_zone_id=99999)

    def test_unknown_region_id_raises_on_update(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(ReferenceDataNotFoundError):
            service.update_substation(
                substation.substation_id, region_id=99999, actor_user_id=actor_user_id
            )

    def test_unknown_state_id_raises_on_update(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(ReferenceDataNotFoundError):
            service.update_substation(
                substation.substation_id, state_id=99999, actor_user_id=actor_user_id
            )

    def test_unknown_grid_owner_id_raises_on_update(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(ReferenceDataNotFoundError):
            service.update_substation(
                substation.substation_id, grid_owner_id=99999, actor_user_id=actor_user_id
            )

    def test_unknown_gm_zone_id_raises_on_update(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(ReferenceDataNotFoundError):
            service.update_substation(
                substation.substation_id, gm_zone_id=99999, actor_user_id=actor_user_id
            )


# --- GM Zone (organizational metadata, independent of Region) -------------------------
class TestGmZoneIndependenceAndEditing:
    """GM Zone is unconditionally required on every Substation, exactly
    like region_id/state_id/grid_owner_id (see migration 0016_gm_zone —
    the temporary nullable/Active-conditional design was tightened once
    every pre-existing Substation had a valid GM Zone assigned). This
    class covers the behaviour that remains distinct from that baseline
    requirement: independence from Region, and editability with audit.
    Requiredness itself is covered by `TestReferenceDataValidation
    .test_unknown_gm_zone_id_raises` and the reference-data existence
    checks shared with region_id/state_id/grid_owner_id."""

    def test_create_with_gm_zone_succeeds(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        assert substation.gm_zone_id == reference_ids.gm_zone_id

    def test_region_and_gm_zone_are_independently_assigned(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """No coupling of any kind between region_id and gm_zone_id — a
        substation may hold any combination of the two (Project Owner:
        "Region and GM Zone represent different engineering metadata and
        must remain separate"). Changing one must never affect the other."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()
        assert substation.region_id == reference_ids.region_id
        assert substation.gm_zone_id == reference_ids.gm_zone_id

        from app.reference_data.models import Region

        other_region = (
            db_session.query(Region).filter(Region.region_id != reference_ids.region_id).first()
        )
        assert other_region is not None
        updated = service.update_substation(
            substation.substation_id, region_id=other_region.region_id, actor_user_id=actor_user_id
        )
        assert updated.region_id == other_region.region_id
        # gm_zone_id is untouched by a region_id-only update.
        assert updated.gm_zone_id == reference_ids.gm_zone_id

    def test_gm_zone_is_editable_and_audited(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        from app.reference_data.models import GmZone
        from app.reference_data.repository import ReferenceDataRepository

        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        other_zone = (
            db_session.query(GmZone).filter(GmZone.gm_zone_id != reference_ids.gm_zone_id).first()
        )
        assert other_zone is not None
        assert ReferenceDataRepository(db_session).get_gm_zone(other_zone.gm_zone_id) is not None

        service.update_substation(
            substation.substation_id, gm_zone_id=other_zone.gm_zone_id, actor_user_id=actor_user_id
        )
        db_session.commit()

        updated = service.get_substation(substation.substation_id)
        assert updated is not None
        assert updated.gm_zone_id == other_zone.gm_zone_id

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "gm_zone_id"
        assert entries[0].old_value == str(reference_ids.gm_zone_id)
        assert entries[0].new_value == str(other_zone.gm_zone_id)

    def test_update_without_gm_zone_argument_leaves_it_unchanged(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """`None` means "not supplied, leave unchanged" for gm_zone_id now
        — mirrors region_id/state_id/grid_owner_id's own plain-`None`
        convention, since gm_zone_id can no longer be legally cleared."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        service.update_substation(
            substation.substation_id, official_name="Renamed", actor_user_id=actor_user_id
        )
        db_session.commit()

        updated = service.get_substation(substation.substation_id)
        assert updated is not None
        assert updated.gm_zone_id == reference_ids.gm_zone_id
        assert updated.official_name == "Renamed"


# --- Region / State / Grid Owner editing (UAT: previously frontend-only gap) ----------
class TestOrganizationalMetadataEditing:
    """Region, State, and Grid Owner were already fully editable at the
    service layer (identical shape to gm_zone_id — validated, audited,
    no-op-safe) — only the frontend's Edit form omitted the controls. This
    class adds the coverage that previously existed only incidentally (via
    `test_region_and_gm_zone_are_independently_assigned`)."""

    def test_editing_state_succeeds_and_audited(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        from app.reference_data.models import State

        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        other_state = (
            db_session.query(State).filter(State.state_id != reference_ids.state_id).first()
        )
        assert other_state is not None

        service.update_substation(
            substation.substation_id, state_id=other_state.state_id, actor_user_id=actor_user_id
        )
        db_session.commit()

        updated = service.get_substation(substation.substation_id)
        assert updated is not None
        assert updated.state_id == other_state.state_id

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "state_id"
        assert entries[0].old_value == str(reference_ids.state_id)
        assert entries[0].new_value == str(other_state.state_id)

    def test_editing_grid_owner_succeeds_and_audited(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        from app.reference_data.models import GridOwner

        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        other_owner = (
            db_session.query(GridOwner)
            .filter(GridOwner.grid_owner_id != reference_ids.grid_owner_id)
            .first()
        )
        assert other_owner is not None

        service.update_substation(
            substation.substation_id,
            grid_owner_id=other_owner.grid_owner_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        updated = service.get_substation(substation.substation_id)
        assert updated is not None
        assert updated.grid_owner_id == other_owner.grid_owner_id

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "grid_owner_id"
        assert entries[0].old_value == str(reference_ids.grid_owner_id)
        assert entries[0].new_value == str(other_owner.grid_owner_id)

    def test_editing_region_state_grid_owner_and_gm_zone_in_one_request(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """All four organizational fields change independently in a single
        request — one audit row per changed field, no cross-field
        derivation or coupling of any kind."""
        from app.reference_data.models import GmZone, GridOwner, Region, State

        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        other_region = (
            db_session.query(Region).filter(Region.region_id != reference_ids.region_id).first()
        )
        other_zone = (
            db_session.query(GmZone).filter(GmZone.gm_zone_id != reference_ids.gm_zone_id).first()
        )
        other_state = (
            db_session.query(State).filter(State.state_id != reference_ids.state_id).first()
        )
        other_owner = (
            db_session.query(GridOwner)
            .filter(GridOwner.grid_owner_id != reference_ids.grid_owner_id)
            .first()
        )
        assert other_region is not None
        assert other_zone is not None
        assert other_state is not None
        assert other_owner is not None

        service.update_substation(
            substation.substation_id,
            region_id=other_region.region_id,
            gm_zone_id=other_zone.gm_zone_id,
            state_id=other_state.state_id,
            grid_owner_id=other_owner.grid_owner_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        updated = service.get_substation(substation.substation_id)
        assert updated is not None
        assert updated.region_id == other_region.region_id
        assert updated.gm_zone_id == other_zone.gm_zone_id
        assert updated.state_id == other_state.state_id
        assert updated.grid_owner_id == other_owner.grid_owner_id

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 4
        field_names = {e.field_name for e in entries}
        assert field_names == {"region_id", "gm_zone_id", "state_id", "grid_owner_id"}

    def test_no_op_update_to_same_organizational_values_writes_no_audit_rows(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        service.update_substation(
            substation.substation_id,
            region_id=reference_ids.region_id,
            gm_zone_id=reference_ids.gm_zone_id,
            state_id=reference_ids.state_id,
            grid_owner_id=reference_ids.grid_owner_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 0


# --- Status transition legality (closed allow-list per ADR-005, revised by ADR-014) ---
class TestStatusTransitionLegality:
    def test_create_may_start_as_under_construction(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(
            service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION"
        )
        assert (
            substation.operational_status_id
            == reference_ids.status_id_by_code["UNDER_CONSTRUCTION"]
        )

    def test_create_may_start_as_active(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        assert substation.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_create_may_not_start_as_decommissioned(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(InvalidStatusTransitionError):
            _create(service, reference_ids, actor_user_id, status_code="DECOMMISSIONED")

    def test_create_may_not_start_as_entered_in_error(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        with pytest.raises(InvalidStatusTransitionError):
            _create(service, reference_ids, actor_user_id, status_code="ENTERED_IN_ERROR")

    def test_create_may_not_start_as_a_removed_lifecycle_state(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Planned, Mothballed, and Retired are no longer part of the
        Substation lifecycle (ADR-014) — the underlying `operational_status`
        reference rows still exist (Equipment Registry's Circuit/Transformer
        independently use Planned/Mothballed/Retired for its own status
        model), but they are no longer legal for a Substation."""
        service = SubstationService(db_session)
        for code in ("PLANNED", "MOTHBALLED", "RETIRED"):
            with pytest.raises(InvalidStatusTransitionError):
                _create(
                    service,
                    reference_ids,
                    actor_user_id,
                    mnemonic=f"X{code[:3]}",
                    status_code=code,
                )

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

    # --- The three legal edges (ADR-014) ---------------------------------------------
    def test_under_construction_to_active_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(
            service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION"
        )
        db_session.commit()

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason="Commissioned",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_active_to_decommissioned_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
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

    def test_under_construction_to_entered_in_error_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(
            service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION"
        )
        db_session.commit()

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            change_reason="Duplicate record",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["ENTERED_IN_ERROR"]

    def test_active_to_entered_in_error_is_legal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()

        result = service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            change_reason="Should never have been created",
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["ENTERED_IN_ERROR"]

    def test_full_under_construction_to_decommissioned_lifecycle(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Exercises the full Under Construction -> Active -> Decommissioned
        path in a single, realistic end-to-end sequence (ADR-014)."""
        service = SubstationService(db_session)
        substation = _create(
            service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION"
        )
        db_session.commit()

        for code in ("ACTIVE", "DECOMMISSIONED"):
            self._advance(service, substation, reference_ids, code, actor_user_id)

        reloaded = service.repo.get_by_id(substation.substation_id)
        assert reloaded is not None
        assert reloaded.operational_status_id == reference_ids.status_id_by_code["DECOMMISSIONED"]

    # --- Rejected transitions --------------------------------------------------------
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

    def test_under_construction_to_decommissioned_directly_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """ADR-014: Under Construction may only reach Active or Entered in
        Error — Decommissioned is only reachable from Active."""
        service = SubstationService(db_session)
        substation = _create(
            service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION"
        )
        db_session.commit()

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["DECOMMISSIONED"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_decommissioned_is_terminal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()
        self._advance(service, substation, reference_ids, "DECOMMISSIONED", actor_user_id)

        with pytest.raises(InvalidStatusTransitionError):
            service.change_status(
                substation.substation_id,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_entered_in_error_is_terminal(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, status_code="ACTIVE")
        db_session.commit()
        self._advance(service, substation, reference_ids, "ENTERED_IN_ERROR", actor_user_id)

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
        substation = _create(
            service, reference_ids, actor_user_id, status_code="UNDER_CONSTRUCTION"
        )
        db_session.commit()

        service.change_status(
            substation.substation_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason="Commissioned ahead of schedule",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "operational_status_id"
        assert entries[0].old_value == "UNDER_CONSTRUCTION"
        assert entries[0].new_value == "ACTIVE"
        assert entries[0].change_reason == "Commissioned ahead of schedule"


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

        for code in ("DECOMMISSIONED",):
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


# --- State is optional (ADR-026) -----------------------------------------------------
class TestOptionalState:
    """State is an administrative attribute, not part of engineering
    identity — it is optional: may be omitted at creation, added later,
    changed, or cleared. region_id/gm_zone_id/grid_owner_id remain
    required and are not affected by these tests."""

    def test_create_without_state_succeeds(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, state_id=None)
        db_session.commit()

        assert substation.state_id is None
        detail = service.get_substation(substation.substation_id)
        assert detail is not None
        assert detail.state_id is None
        # Creation writes no audit rows (accountability is on the row itself).
        _entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 0

    def test_create_with_state_still_supported(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()
        assert substation.state_id == reference_ids.state_id

    def test_create_with_unknown_state_id_still_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Optionality must not weaken validation — a *supplied* State must
        still exist in reference data."""
        service = SubstationService(db_session)
        with pytest.raises(ReferenceDataNotFoundError):
            _create(service, reference_ids, actor_user_id, state_id=999_999)

    def test_add_state_to_a_stateless_substation(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id, state_id=None)
        db_session.commit()

        service.update_substation(
            substation.substation_id, state_id=reference_ids.state_id, actor_user_id=actor_user_id
        )
        db_session.commit()

        detail = service.get_substation(substation.substation_id)
        assert detail is not None
        assert detail.state_id == reference_ids.state_id

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "state_id"
        assert entries[0].old_value is None
        assert entries[0].new_value == str(reference_ids.state_id)

    def test_clear_existing_state_by_sending_null(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        service.update_substation(
            substation.substation_id, state_id=None, actor_user_id=actor_user_id
        )
        db_session.commit()

        detail = service.get_substation(substation.substation_id)
        assert detail is not None
        assert detail.state_id is None

        entries, total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "state_id"
        assert entries[0].old_value == str(reference_ids.state_id)
        assert entries[0].new_value is None

    def test_omitting_state_leaves_it_unchanged(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """Not supplying state_id (the `...` sentinel) must never clear it —
        only an explicit null clears. Updating another field must leave
        State untouched and write no state_id audit row."""
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()

        service.update_substation(
            substation.substation_id, remarks="only remarks changed", actor_user_id=actor_user_id
        )
        db_session.commit()

        detail = service.get_substation(substation.substation_id)
        assert detail is not None
        assert detail.state_id == reference_ids.state_id
        entries, _total = service.list_audit_log(substation.substation_id, page=1, page_size=50)
        assert not any(e.field_name == "state_id" for e in entries)

    def test_update_with_unknown_state_id_still_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = SubstationService(db_session)
        substation = _create(service, reference_ids, actor_user_id)
        db_session.commit()
        with pytest.raises(ReferenceDataNotFoundError):
            service.update_substation(
                substation.substation_id, state_id=999_999, actor_user_id=actor_user_id
            )

    def test_filter_by_state_excludes_stateless_substations(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        """A specific-State filter still works and a null-State substation
        simply does not match it (no placeholder, no special bucket)."""
        service = SubstationService(db_session)
        with_state = _create(
            service, reference_ids, actor_user_id, mnemonic="WSUB", official_name="With State"
        )
        without_state = _create(
            service,
            reference_ids,
            actor_user_id,
            mnemonic="NSUB",
            official_name="No State",
            state_id=None,
        )
        db_session.commit()

        items, total = service.list_substations(
            page=1, page_size=50, state_id=reference_ids.state_id
        )
        ids = {s.substation_id for s in items}
        assert with_state.substation_id in ids
        assert without_state.substation_id not in ids
        assert total == 1
