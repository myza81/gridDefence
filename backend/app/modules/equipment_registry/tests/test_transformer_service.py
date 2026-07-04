"""Business rule tests for EquipmentRegistryService's Transformer Registry
(Phase 3.5) — equipment-registry-module.md's Transformer Registry section,
ADR-008's Transformer Registry addendum, and its two UAT-correction addenda
(#1: transformers are substation-owned equipment, never modeled as spanning
two substations; #2: transformer-number uniqueness is scoped to the HV/LV
switchyard pair, not the whole substation).

Covers: substation-first two-terminal (HV/LV) creation, generated
short-name computation across the full TNB prefix table, HV/LV
voltage-order validation, same-switchyard rejection, HV/LV-must-belong-to-
the-selected-substation rejection, duplicate-transformer-identity uniqueness
scoped to `(substation_id, hv_switchyard_id, lv_switchyard_id,
transformer_number)` on both create and update (and what it deliberately
does NOT reject — parallel transformers, same number at unrelated
substations, same number reused across a different HV/LV pair at the same
substation), breaker-number override (never rejected by the backend), edit,
search/filter (including by substation), and audit logging.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.modules.equipment_registry.exceptions import (
    DuplicateTransformerError,
    InvalidTransformerInitialStatusError,
    InvalidTransformerVoltageOrderError,
    NotFoundError,
    ReferenceDataNotFoundError,
    SameSwitchyardTerminalsError,
    SubstationNotFoundError,
    TransformerYardSubstationMismatchError,
    VoltageYardNotFoundError,
)
from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.equipment_registry.tests.conftest import ReferenceIds
from app.reference_data.models import VoltageLevel


def _voltage_level_id(db_session: Session, label: str) -> int:
    return db_session.query(VoltageLevel).filter_by(label=label).one().voltage_level_id


def _create_yard(
    service: EquipmentRegistryService,
    db_session: Session,
    *,
    substation_id: uuid.UUID,
    voltage_level_label: str,
    actor_user_id: uuid.UUID,
) -> uuid.UUID:
    yard = service.create_voltage_yard(
        substation_id=substation_id,
        voltage_level_id=_voltage_level_id(db_session, voltage_level_label),
        actor_user_id=actor_user_id,
    )
    db_session.commit()
    return yard.voltage_yard_id


def _create_transformer(
    service: EquipmentRegistryService,
    ref: ReferenceIds,
    *,
    substation_id: uuid.UUID,
    transformer_number: str,
    hv_switchyard_id: uuid.UUID,
    lv_switchyard_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    hv_breaker_number: str = "H10",
    lv_breaker_number: str = "110",
    status_code: str = "ACTIVE",
):
    return service.create_transformer(
        substation_id=substation_id,
        transformer_number=transformer_number,
        hv_switchyard_id=hv_switchyard_id,
        hv_breaker_number=hv_breaker_number,
        lv_switchyard_id=lv_switchyard_id,
        lv_breaker_number=lv_breaker_number,
        capacity_mva=None,
        commissioning_date=None,
        operational_status_id=ref.status_id_by_code[status_code],
        transformer_type=None,
        manufacturer=None,
        remarks=None,
        actor_user_id=actor_user_id,
    )


# --- Substation-first two-terminal (HV/LV) creation and generated short name -------------
class TestTransformerCreation:
    def test_creates_transformer_with_hv_and_lv_terminals_at_its_own_substation(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """PKLG has both a 500kV yard (voltage_yard_ids) and a 132kV yard
        (lv_voltage_yard_ids) — the normal, legitimate case: a transformer
        stepping between two voltage levels at its own substation."""
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.substation_id == substation_ids["PKLG"]
        assert detail.substation_mnemonic == "PKLG"
        assert len(detail.terminals) == 2
        assert {t.side for t in detail.terminals} == {"HV", "LV"}
        assert {t.substation_mnemonic for t in detail.terminals} == {"PKLG"}

    def test_generated_short_name_is_computed_not_stored(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """voltage_yard_ids is 500kV, lv_voltage_yard_ids is 132kV — HV
        prefix for 500kV is "XGT" (TNB convention)."""
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="2",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.generated_short_name == "XGT2"
        # Not a persisted column — Transformer the ORM model has no such
        # attribute at all (would raise AttributeError if it existed as a
        # stored field a caller could read directly off the row).
        assert not hasattr(transformer, "generated_short_name")

    @pytest.mark.parametrize(
        ("hv_label", "lv_label", "expected_prefix"),
        [
            ("500kV", "275kV", "XGT"),
            ("275kV", "132kV", "SGT"),
            ("230kV", "132kV", "SGT"),
            ("132kV", "33kV", "T"),
            ("132kV", "11kV", "T"),
        ],
    )
    def test_generated_short_name_prefix_matches_tnb_convention(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
        hv_label: str,
        lv_label: str,
        expected_prefix: str,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        hv_yard = _create_yard(
            service,
            db_session,
            substation_id=substation_ids["PKLG"],
            voltage_level_label=hv_label,
            actor_user_id=actor_user_id,
        )
        lv_yard = _create_yard(
            service,
            db_session,
            substation_id=substation_ids["PKLG"],
            voltage_level_label=lv_label,
            actor_user_id=actor_user_id,
        )
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="3",
            hv_switchyard_id=hv_yard,
            lv_switchyard_id=lv_yard,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.generated_short_name == f"{expected_prefix}3"

    def test_invalid_initial_status_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InvalidTransformerInitialStatusError):
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
                status_code="RETIRED",
            )

    def test_nonexistent_substation_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(SubstationNotFoundError):
            _create_transformer(
                service,
                reference_ids,
                substation_id=uuid.uuid4(),
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )

    def test_nonexistent_hv_switchyard_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(VoltageYardNotFoundError):
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=uuid.uuid4(),
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )

    def test_invalid_operational_status_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(ReferenceDataNotFoundError):
            service.create_transformer(
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                hv_breaker_number="H10",
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                lv_breaker_number="110",
                capacity_mva=None,
                commissioning_date=None,
                operational_status_id=99999,
                transformer_type=None,
                manufacturer=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )


# --- HV/LV validation rules, including the UAT-corrected substation rule -----------------
class TestTransformerVoltageOrderAndSwitchyardRules:
    def test_hv_and_lv_at_the_same_switchyard_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(SameSwitchyardTerminalsError):
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )

    def test_reversed_hv_lv_order_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """voltage_yard_ids is 500kV, lv_voltage_yard_ids is 132kV —
        supplying the 132kV yard as HV and the 500kV yard as LV must be
        rejected (132 -> 500 is a reversed step-up, not a real HV/LV
        transformer orientation)."""
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InvalidTransformerVoltageOrderError):
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                lv_switchyard_id=voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )

    # Note: an "equal HV/LV voltage level via two distinct switchyards"
    # scenario is no longer constructible now that both switchyards must
    # belong to the same substation (this UAT correction) — a substation
    # can hold at most one switchyard per voltage level
    # (uq_substation_voltage_yard), so two same-substation, same-level
    # switchyards would necessarily be the same row, which is already
    # covered by test_hv_and_lv_at_the_same_switchyard_is_rejected above.
    # The service layer's `hv_level.nominal_kv <= lv_level.nominal_kv`
    # check remains (defensive; also backs the reversed-order case below).

    def test_hv_yard_belonging_to_a_different_substation_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """UAT blocker fix: a transformer is substation-owned equipment —
        its HV and LV switchyards must both belong to the substation it is
        created at. Here the selected substation is PKLG but the LV
        switchyard belongs to IGBK."""
        service = EquipmentRegistryService(db_session)
        with pytest.raises(TransformerYardSubstationMismatchError) as excinfo:
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["IGBK"],
                actor_user_id=actor_user_id,
            )
        assert "LV" in str(excinfo.value)
        assert "PKLG" in str(excinfo.value)
        assert "IGBK" in str(excinfo.value)

    def test_lv_yard_belonging_to_a_different_substation_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """Same rule, HV side: selected substation is IGBK but the HV
        switchyard belongs to PKLG."""
        service = EquipmentRegistryService(db_session)
        with pytest.raises(TransformerYardSubstationMismatchError) as excinfo:
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["IGBK"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["IGBK"],
                actor_user_id=actor_user_id,
            )
        assert "HV" in str(excinfo.value)

    def test_cross_substation_transformers_are_not_permitted_even_when_not_flagged_by_voltage_order(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """A transformer must never be modeled as spanning two substations
        — this is rejected regardless of which substation_id is selected,
        since at least one side will always mismatch it."""
        service = EquipmentRegistryService(db_session)
        for selected in (substation_ids["PKLG"], substation_ids["IGBK"]):
            with pytest.raises(TransformerYardSubstationMismatchError):
                _create_transformer(
                    service,
                    reference_ids,
                    substation_id=selected,
                    transformer_number="X",
                    hv_switchyard_id=voltage_yard_ids["PKLG"],
                    lv_switchyard_id=lv_voltage_yard_ids["IGBK"],
                    actor_user_id=actor_user_id,
                )


# --- Duplicate transformer identity (UAT-corrected uniqueness rule) ----------------------
class TestTransformerUniqueness:
    def test_duplicate_transformer_number_at_the_same_substation_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(DuplicateTransformerError) as excinfo:
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )
        # Human-readable substation mnemonic, not a raw id.
        assert "PKLG" in str(excinfo.value)

    def test_parallel_transformers_at_the_same_substation_are_allowed(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """T1 and T2 both stepping PKLG's own 500kV yard down to PKLG's own
        132kV yard — a normal N-1 redundancy configuration, not a
        duplicate, since the transformer numbers differ."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        second = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="2",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert second is not None

    def test_same_transformer_number_at_a_different_substation_is_allowed(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """ "1" at PKLG and "1" (same transformer_number) at IGBK are
        unrelated, legitimate transformers — the uniqueness rule is scoped
        to (substation_id, transformer_number), not global, and must not
        collide them just because they'd generate the same engineering
        short name."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        second = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["IGBK"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["IGBK"],
            lv_switchyard_id=lv_voltage_yard_ids["IGBK"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert second is not None

    def test_same_transformer_number_across_different_hv_lv_pairs_at_one_substation_is_allowed(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """UAT regression: a substation legitimately has a "Transformer Bay
        1" on its 500/132kV pair *and a separate* "Transformer Bay 1" on its
        132/33kV pair — real Malaysian grid practice numbers transformer
        bays per transformation pair, not per substation as a whole. The
        superseded `UNIQUE(substation_id, transformer_number)` constraint
        incorrectly rejected this."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        tertiary_yard_id = _create_yard(
            service,
            db_session,
            substation_id=substation_ids["PKLG"],
            voltage_level_label="33kV",
            actor_user_id=actor_user_id,
        )
        second = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            lv_switchyard_id=tertiary_yard_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert second is not None

    def test_same_substation_and_hv_lv_pair_and_number_is_still_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """The corrected rule still rejects the genuine duplicate case: same
        substation, same HV/LV switchyard pair, same transformer number."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(DuplicateTransformerError) as excinfo:
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )
        assert "PKLG" in str(excinfo.value)


# --- Uniqueness excludes ENTERED_IN_ERROR transformers (UAT correction #3) ------------------
class TestTransformerUniquenessExcludesEnteredInError:
    """UAT found that a transformer corrected to `ENTERED_IN_ERROR` still
    permanently occupied its `(substation, HV yard, LV yard, number)`
    identity, blocking a legitimate re-creation with the same identity even
    though the corrected record is already hidden from every default view.
    Deletion/correction policy: an `ENTERED_IN_ERROR` record is "not a real
    engineering asset" and must not reserve that identity forever. The
    corrected record itself is never deleted — only excluded from this
    uniqueness check — so it stays reachable by id and fully audit-visible."""

    def test_entered_in_error_transformer_does_not_block_recreating_the_same_identity(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        mistaken = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        service.update_transformer(
            mistaken.transformer_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        recreated = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        assert recreated is not None
        assert recreated.transformer_id != mistaken.transformer_id

        # The corrected record is preserved, not deleted — still reachable
        # directly by id, audit history intact.
        mistaken_detail = service.get_transformer(mistaken.transformer_id)
        assert mistaken_detail is not None
        assert (
            mistaken_detail.operational_status_id
            == reference_ids.status_id_by_code["ENTERED_IN_ERROR"]
        )

    def test_active_transformer_still_blocks_a_genuine_duplicate(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """The exclusion is specific to ENTERED_IN_ERROR — an ACTIVE
        transformer on the same identity must still block a duplicate
        (re-verifies `test_same_substation_and_hv_lv_pair_and_number_is_still_rejected`
        under this fix, from this correction's own explicit acceptance
        criteria)."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(DuplicateTransformerError):
            _create_transformer(
                service,
                reference_ids,
                substation_id=substation_ids["PKLG"],
                transformer_number="1",
                hv_switchyard_id=voltage_yard_ids["PKLG"],
                lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
                actor_user_id=actor_user_id,
            )

    def test_entered_in_error_transformer_does_not_block_renaming_into_its_identity(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """Same exclusion applies to `update_transformer`'s own uniqueness
        check, not just `create_transformer`'s."""
        service = EquipmentRegistryService(db_session)
        mistaken = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        service.update_transformer(
            mistaken.transformer_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        other = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="2",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            other.transformer_id, transformer_number="1", actor_user_id=actor_user_id
        )
        db_session.commit()

        detail = service.get_transformer(other.transformer_id)
        assert detail is not None
        assert detail.transformer_number == "1"


# --- Update (metadata + breaker override) -------------------------------------------------
class TestTransformerUpdate:
    def test_renaming_a_transformer_number_to_collide_with_its_own_pair_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """`update_transformer` previously performed no uniqueness check at
        all — renaming "2" to "1" on the same HV/LV pair as an existing "1"
        must be rejected, exactly like creation."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        second = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="2",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(DuplicateTransformerError) as excinfo:
            service.update_transformer(
                second.transformer_id, transformer_number="1", actor_user_id=actor_user_id
            )
        assert "PKLG" in str(excinfo.value)

    def test_renaming_a_transformer_number_used_only_by_a_different_pair_is_allowed(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """Renaming to a number already used by a *different* HV/LV pair at
        the same substation must be allowed — the uniqueness scope is the
        pair, not the whole substation."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        tertiary_yard_id = _create_yard(
            service,
            db_session,
            substation_id=substation_ids["PKLG"],
            voltage_level_label="33kV",
            actor_user_id=actor_user_id,
        )
        other_pair_transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="2",
            hv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            lv_switchyard_id=tertiary_yard_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            other_pair_transformer.transformer_id,
            transformer_number="1",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(other_pair_transformer.transformer_id)
        assert detail is not None
        assert detail.transformer_number == "1"

    def test_renaming_a_transformer_to_its_own_current_number_is_a_no_op(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """A transformer must never collide with itself when "renamed" to
        the number it already has."""
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            transformer.transformer_id, transformer_number="1", actor_user_id=actor_user_id
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.transformer_number == "1"

    def test_update_transformer_number_capacity_and_metadata(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            transformer.transformer_id,
            transformer_number="1A",
            capacity_mva=90.0,
            commissioning_date=date(2020, 6, 1),
            transformer_type="Auto",
            manufacturer="ABB",
            remarks="Uprated",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.transformer_number == "1A"
        assert float(detail.capacity_mva) == pytest.approx(90.0)
        assert detail.commissioning_date == date(2020, 6, 1)
        assert detail.transformer_type == "Auto"
        assert detail.manufacturer == "ABB"
        assert detail.remarks == "Uprated"
        # substation_id remains untouched by update_transformer — no
        # parameter even exists to change it (UAT correction).
        assert detail.substation_id == substation_ids["PKLG"]

    def test_override_hv_and_lv_breaker_numbers_is_never_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """The backend must never reject a custom breaker number — the
        suggested value is a frontend-only convenience."""
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
            hv_breaker_number="H10",
            lv_breaker_number="110",
        )
        db_session.commit()

        service.update_transformer(
            transformer.transformer_id,
            hv_breaker_number="WHATEVER-1",
            lv_breaker_number="ANYTHING-2",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        hv_terminal = next(t for t in detail.terminals if t.side == "HV")
        lv_terminal = next(t for t in detail.terminals if t.side == "LV")
        assert hv_terminal.breaker_number == "WHATEVER-1"
        assert lv_terminal.breaker_number == "ANYTHING-2"

    def test_update_operational_status(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            transformer.transformer_id,
            operational_status_id=reference_ids.status_id_by_code["MOTHBALLED"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.operational_status_id == reference_ids.status_id_by_code["MOTHBALLED"]

    def test_partial_update_leaves_unsupplied_fields_unchanged(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        service.update_transformer(
            transformer.transformer_id,
            manufacturer="Siemens",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            transformer.transformer_id,
            capacity_mva=120.0,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_transformer(transformer.transformer_id)
        assert detail is not None
        assert detail.manufacturer == "Siemens"
        assert float(detail.capacity_mva) == pytest.approx(120.0)

    def test_update_unknown_transformer_raises_not_found(
        self, db_session: Session, actor_user_id: uuid.UUID
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(NotFoundError):
            service.update_transformer(
                uuid.uuid4(), transformer_number="1", actor_user_id=actor_user_id
            )


# --- Read / list / search, including substation-based discovery --------------------------
class TestTransformerReadAndSearch:
    def test_get_nonexistent_transformer_returns_none(self, db_session: Session) -> None:
        service = EquipmentRegistryService(db_session)
        assert service.get_transformer(uuid.uuid4()) is None

    def test_list_transformers_search_by_transformer_number(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="UNIQUE-NUM",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        items, total = service.list_transformers(page=1, page_size=50, search="unique-num")
        assert total == 1
        assert items[0].transformer_number == "UNIQUE-NUM"

    def test_list_transformers_search_by_substation_mnemonic(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        items, total = service.list_transformers(page=1, page_size=50, search="pklg")
        assert total == 1
        assert items[0].substation_mnemonic == "PKLG"

        no_match_items, no_match_total = service.list_transformers(
            page=1, page_size=50, search="nope"
        )
        assert no_match_total == 0
        assert no_match_items == []

    def test_list_transformers_filter_by_substation_id(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """From a substation's own perspective: "which transformers are
        installed here" — the exact UAT-reported requirement."""
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["IGBK"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["IGBK"],
            lv_switchyard_id=lv_voltage_yard_ids["IGBK"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        pklg_items, pklg_total = service.list_transformers(
            page=1, page_size=50, substation_id=substation_ids["PKLG"]
        )
        assert pklg_total == 1
        assert pklg_items[0].substation_mnemonic == "PKLG"

        igbk_items, igbk_total = service.list_transformers(
            page=1, page_size=50, substation_id=substation_ids["IGBK"]
        )
        assert igbk_total == 1
        assert igbk_items[0].substation_mnemonic == "IGBK"

    def test_list_transformers_filter_by_operational_status(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
            status_code="PLANNED",
        )
        db_session.commit()

        active_items, active_total = service.list_transformers(
            page=1, page_size=50, operational_status_id=reference_ids.status_id_by_code["ACTIVE"]
        )
        assert active_total == 0
        assert active_items == []

        planned_items, planned_total = service.list_transformers(
            page=1, page_size=50, operational_status_id=reference_ids.status_id_by_code["PLANNED"]
        )
        assert planned_total == 1


# --- Audit logging ---------------------------------------------------------------------------
class TestTransformerAuditLogging:
    def test_create_writes_no_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        _entries, total = service.list_transformer_audit_log(
            transformer.transformer_id, page=1, page_size=50
        )
        assert total == 0

    def test_update_writes_one_audit_row_per_changed_field_including_breaker_numbers(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        transformer = _create_transformer(
            service,
            reference_ids,
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_transformer(
            transformer.transformer_id,
            manufacturer="Siemens",
            hv_breaker_number="H99",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_transformer_audit_log(
            transformer.transformer_id, page=1, page_size=50
        )
        assert total == 2
        field_names = {e.field_name for e in entries}
        assert field_names == {"manufacturer", "hv_breaker_number"}
