"""Business rule tests for EquipmentRegistryService — docs/architecture/
equipment-registry-module.md §9 (Business Rules), §10 (Validation Rules),
§7.5a (SubstationVoltageYard; ADR-008).

Covers this phase's mandated test list plus the Phase 3 UAT fix package:
two-terminal creation, tee-off/N-terminal creation, bay_number-vs-
breaker_number field placement, validation failures, search/filter/list
behaviour, multi-voltage substations (SubstationVoltageYard), full circuit
edit (bay number/status/line type/voltage level), and per-terminal edit
(breaker number/commissioning date/remarks).
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.equipment_registry.exceptions import (
    DuplicateTerminalVoltageYardError,
    DuplicateVoltageYardError,
    InsufficientActiveTerminalsForActivationError,
    InsufficientTerminalsError,
    InvalidGeolocationPairError,
    InvalidInitialStatusError,
    NotFoundError,
    ReferenceDataNotFoundError,
    SubstationNotFoundError,
    SwitchyardEnteredInErrorError,
    SwitchyardHasActiveReferencesError,
    TerminalVoltageLevelMismatchError,
    VoltageYardNotFoundError,
)
from app.modules.equipment_registry.service import EquipmentRegistryService, TerminalInput
from app.modules.equipment_registry.tests.conftest import ReferenceIds
from app.reference_data.models import LineType


def _two_terminals(voltage_yard_ids: dict[str, uuid.UUID]) -> list[TerminalInput]:
    return [
        TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L25"),
        TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="805"),
    ]


def _create_circuit(
    service: EquipmentRegistryService,
    ref: ReferenceIds,
    voltage_yard_ids: dict[str, uuid.UUID],
    actor_user_id: uuid.UUID,
    *,
    bay_number: str = "Line 1",
    status_code: str = "ACTIVE",
    terminals: list[TerminalInput] | None = None,
    is_interconnector: bool = False,
):
    return service.create_circuit(
        bay_number=bay_number,
        voltage_level_id=ref.voltage_level_id,
        line_type_id=ref.line_type_id,
        operational_status_id=ref.status_id_by_code[status_code],
        is_interconnector=is_interconnector,
        remarks=None,
        terminals=terminals if terminals is not None else _two_terminals(voltage_yard_ids),
        actor_user_id=actor_user_id,
    )


# --- Two-terminal circuit creation (mandated) ------------------------------------------
class TestTwoTerminalCircuitCreation:
    def test_creates_circuit_with_two_terminals(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        terminals = service.list_terminals(circuit.circuit_id)
        assert len(terminals) == 2
        assert {t.substation_mnemonic for t in terminals} == {"PKLG", "IGBK"}

    def test_computed_circuit_name_is_the_sorted_terminal_mnemonics_only_never_bay_number(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """Phase 3 close-out: `circuit_name` is the canonical route only —
        `bay_number` is never embedded (previously produced a
        duplicated-looking display when the UI also showed `bay_number`
        separately), and mnemonics are sorted deterministically, not
        joined in terminal-insertion order (previously produced
        "PKLG–IGBK" or "IGBK–PKLG" for the same physical circuit depending
        on entry order)."""
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, bay_number="1"
        )
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        # _two_terminals() supplies PKLG then IGBK, in that order — the
        # canonical name is alphabetical ("IGBK" < "PKLG"), not insertion
        # order, and does not contain "1" (the bay number) anywhere.
        assert detail.circuit_name == "IGBK–PKLG"
        assert detail.bay_number == "1"

    def test_circuit_name_is_deterministic_regardless_of_terminal_entry_order(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        forward = _create_circuit(
            service,
            reference_ids,
            voltage_yard_ids,
            actor_user_id,
            bay_number="1",
            terminals=[
                TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L1"),
                TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L2"),
            ],
        )
        reversed_order = _create_circuit(
            service,
            reference_ids,
            voltage_yard_ids,
            actor_user_id,
            bay_number="2",
            terminals=[
                TerminalInput(voltage_yard_id=voltage_yard_ids["IGBK"], breaker_number="L3"),
                TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L4"),
            ],
        )
        db_session.commit()

        forward_detail = service.get_circuit(forward.circuit_id)
        reversed_detail = service.get_circuit(reversed_order.circuit_id)
        assert forward_detail is not None
        assert reversed_detail is not None
        assert forward_detail.circuit_name == reversed_detail.circuit_name == "IGBK–PKLG"


# --- Tee-off / multi-terminal circuit creation (mandated) -------------------------------
class TestTeeOffCircuitCreation:
    def test_creates_circuit_with_three_terminals(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        terminals = [
            TerminalInput(voltage_yard_id=voltage_yard_ids["ABBA"], breaker_number="A1"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="S1"),
            TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="N1"),
        ]
        circuit = _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, terminals=terminals
        )
        db_session.commit()

        listed = service.list_terminals(circuit.circuit_id)
        assert len(listed) == 3
        assert {t.substation_mnemonic for t in listed} == {"ABBA", "PKLG", "NKST"}

    def test_add_terminal_extends_a_two_terminal_circuit_into_a_tee_off(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        service.add_terminal(
            circuit.circuit_id,
            voltage_yard_id=voltage_yard_ids["NKST"],
            breaker_number="N1",
            commissioning_date=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        terminals = service.list_terminals(circuit.circuit_id)
        assert len(terminals) == 3
        assert {t.substation_mnemonic for t in terminals} == {"PKLG", "IGBK", "NKST"}

    def test_adding_a_terminal_writes_an_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        service.add_terminal(
            circuit.circuit_id,
            voltage_yard_id=voltage_yard_ids["NKST"],
            breaker_number="N1",
            commissioning_date=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "terminal_added"
        assert "NKST" in entries[0].new_value


# --- Multi-voltage substations (Phase 3 UAT fix package; ADR-008) -----------------------
class TestMultiVoltageSubstations:
    def test_a_substation_may_have_more_than_one_voltage_yard(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """docs/architecture/equipment-registry-module.md §7.5a's own
        example: PKLG with both a 275kV-equivalent and a 132kV-equivalent
        yard."""
        service = EquipmentRegistryService(db_session)
        first_yard = service.create_voltage_yard(
            substation_id=substation_ids["PKLG"],
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        second_yard = service.create_voltage_yard(
            substation_id=substation_ids["PKLG"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        yards = service.list_voltage_yards(substation_id=substation_ids["PKLG"])
        assert {y.voltage_yard_id for y in yards} == {
            first_yard.voltage_yard_id,
            second_yard.voltage_yard_id,
        }
        labels = {y.display_label for y in yards}
        assert labels == {"PKLG — 500kV", "PKLG — 132kV"}

    def test_duplicate_voltage_yard_for_same_substation_and_level_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        service.create_voltage_yard(
            substation_id=substation_ids["PKLG"],
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(DuplicateVoltageYardError) as excinfo:
            service.create_voltage_yard(
                substation_id=substation_ids["PKLG"],
                voltage_level_id=reference_ids.voltage_level_id,
                actor_user_id=actor_user_id,
            )
        # UAT regression: the message must be human-readable (substation
        # mnemonic + voltage level label), not raw UUIDs/internal ids — a
        # message like "voltage level '4'" gives an engineer no way to know
        # that means 132kV.
        assert "PKLG" in str(excinfo.value)
        assert "500kV" in str(excinfo.value)
        assert str(reference_ids.voltage_level_id) not in str(excinfo.value)

    def test_voltage_yard_for_nonexistent_substation_is_rejected(
        self, db_session: Session, reference_ids: ReferenceIds, actor_user_id: uuid.UUID
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(SubstationNotFoundError):
            service.create_voltage_yard(
                substation_id=uuid.uuid4(),
                voltage_level_id=reference_ids.voltage_level_id,
                actor_user_id=actor_user_id,
            )

    def test_rule_6_is_scoped_to_voltage_yards_not_substations_for_terminals_at_the_same_level(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """Business rule 6 is scoped to voltage yards, not substations
        (§7.5a; ADR-008) — distinct voltage yards at different substations,
        all sharing the circuit's own voltage level, is legal. (Note: prior
        to the rule 6a terminal-voltage-level guardrail, this scenario was
        demonstrated using two DIFFERENT voltage levels at the SAME
        substation — see ADR-008's addendum for why rule 6a makes that
        specific example no longer constructible.)"""
        service = EquipmentRegistryService(db_session)
        pklg_yard = service.create_voltage_yard(
            substation_id=substation_ids["PKLG"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        igbk_yard = service.create_voltage_yard(
            substation_id=substation_ids["IGBK"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        circuit = service.create_circuit(
            bay_number="Line 1",
            voltage_level_id=second_voltage_level_id,
            line_type_id=reference_ids.line_type_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            is_interconnector=False,
            remarks=None,
            terminals=[
                TerminalInput(voltage_yard_id=pklg_yard.voltage_yard_id, breaker_number="L1"),
                TerminalInput(voltage_yard_id=igbk_yard.voltage_yard_id, breaker_number="L2"),
            ],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        terminals = service.list_terminals(circuit.circuit_id)
        assert len(terminals) == 2
        assert {t.substation_mnemonic for t in terminals} == {"PKLG", "IGBK"}
        assert {t.voltage_level_label for t in terminals} == {"132kV"}


# --- SubstationVoltageYard metadata (Phase 3 UAT follow-up) ------------------------------
class TestVoltageYardMetadata:
    def test_create_with_all_metadata_succeeds(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard = service.create_voltage_yard(
            substation_id=substation_ids["ABBA"],
            voltage_level_id=reference_ids.voltage_level_id,
            commissioning_date=date(2020, 6, 1),
            latitude=3.140853,
            longitude=101.693207,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        summaries = service.list_voltage_yards(substation_id=substation_ids["ABBA"])
        assert len(summaries) == 1
        assert summaries[0].voltage_yard_id == yard.voltage_yard_id
        assert summaries[0].commissioning_date == date(2020, 6, 1)
        assert float(summaries[0].latitude) == pytest.approx(3.140853)
        assert float(summaries[0].longitude) == pytest.approx(101.693207)

    def test_create_with_no_metadata_leaves_all_three_fields_null(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        service.create_voltage_yard(
            substation_id=substation_ids["ABBA"],
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        summaries = service.list_voltage_yards(substation_id=substation_ids["ABBA"])
        assert summaries[0].commissioning_date is None
        assert summaries[0].latitude is None
        assert summaries[0].longitude is None

    def test_create_with_latitude_but_no_longitude_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InvalidGeolocationPairError):
            service.create_voltage_yard(
                substation_id=substation_ids["ABBA"],
                voltage_level_id=reference_ids.voltage_level_id,
                latitude=3.14,
                longitude=None,
                actor_user_id=actor_user_id,
            )

    def test_create_with_longitude_but_no_latitude_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InvalidGeolocationPairError):
            service.create_voltage_yard(
                substation_id=substation_ids["ABBA"],
                voltage_level_id=reference_ids.voltage_level_id,
                latitude=None,
                longitude=101.7,
                actor_user_id=actor_user_id,
            )

    def test_update_sets_commissioning_date_and_geolocation(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard = service.create_voltage_yard(
            substation_id=substation_ids["ABBA"],
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_voltage_yard(
            yard.voltage_yard_id,
            commissioning_date=date(2021, 3, 15),
            latitude=3.0,
            longitude=101.5,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        summaries = service.list_voltage_yards(substation_id=substation_ids["ABBA"])
        assert summaries[0].commissioning_date == date(2021, 3, 15)
        assert float(summaries[0].latitude) == pytest.approx(3.0)
        assert float(summaries[0].longitude) == pytest.approx(101.5)

    def test_update_can_clear_metadata_back_to_null(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard = service.create_voltage_yard(
            substation_id=substation_ids["ABBA"],
            voltage_level_id=reference_ids.voltage_level_id,
            commissioning_date=date(2020, 1, 1),
            latitude=3.0,
            longitude=101.5,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_voltage_yard(
            yard.voltage_yard_id,
            commissioning_date=None,
            latitude=None,
            longitude=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        summaries = service.list_voltage_yards(substation_id=substation_ids["ABBA"])
        assert summaries[0].commissioning_date is None
        assert summaries[0].latitude is None
        assert summaries[0].longitude is None

    def test_partial_update_leaves_unsupplied_fields_unchanged(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard = service.create_voltage_yard(
            substation_id=substation_ids["ABBA"],
            voltage_level_id=reference_ids.voltage_level_id,
            commissioning_date=date(2020, 1, 1),
            latitude=3.0,
            longitude=101.5,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        # Only commissioning_date supplied — latitude/longitude untouched
        # (service-level Ellipsis-sentinel default, not passed at all here).
        service.update_voltage_yard(
            yard.voltage_yard_id,
            commissioning_date=date(2022, 9, 9),
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        summaries = service.list_voltage_yards(substation_id=substation_ids["ABBA"])
        assert summaries[0].commissioning_date == date(2022, 9, 9)
        assert float(summaries[0].latitude) == pytest.approx(3.0)
        assert float(summaries[0].longitude) == pytest.approx(101.5)

    def test_update_unknown_voltage_yard_raises_not_found(
        self, db_session: Session, actor_user_id: uuid.UUID
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(VoltageYardNotFoundError):
            service.update_voltage_yard(
                uuid.uuid4(), commissioning_date=date(2020, 1, 1), actor_user_id=actor_user_id
            )

    def test_existing_voltage_yards_created_before_this_feature_remain_valid_with_nulls(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
    ) -> None:
        """The `voltage_yard_ids` fixture creates yards the same way this
        migration's pre-existing rows were left — no metadata supplied —
        proving old rows remain valid with NULLs, not requiring backfill."""
        service = EquipmentRegistryService(db_session)
        summaries = service.list_voltage_yards()
        assert len(summaries) == len(voltage_yard_ids)
        assert all(s.commissioning_date is None for s in summaries)
        assert all(s.latitude is None for s in summaries)
        assert all(s.longitude is None for s in summaries)


# --- bay_number vs breaker_number placement (mandated) -----------------------------------
class TestBayNumberVsBreakerNumberPlacement:
    def test_bay_number_is_owned_by_the_circuit_and_shared_across_terminals(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, bay_number="Line 1"
        )
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        assert detail.bay_number == "Line 1"
        # bay_number lives once, on the Circuit — not duplicated per terminal.
        assert not hasattr(detail.terminals[0], "bay_number")

    def test_breaker_number_is_independently_numbered_per_terminal(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        terminals = {t.substation_mnemonic: t for t in service.list_terminals(circuit.circuit_id)}
        assert terminals["PKLG"].breaker_number == "L25"
        assert terminals["IGBK"].breaker_number == "805"
        assert terminals["PKLG"].breaker_number != terminals["IGBK"].breaker_number


# --- Validation failures (mandated) -----------------------------------------------------
class TestValidationFailures:
    def test_fewer_than_two_terminals_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InsufficientTerminalsError):
            _create_circuit(
                service,
                reference_ids,
                voltage_yard_ids,
                actor_user_id,
                terminals=[
                    TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L25")
                ],
            )

    def test_zero_terminals_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InsufficientTerminalsError):
            _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id, terminals=[])

    def test_duplicate_voltage_yard_among_supplied_terminals_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(DuplicateTerminalVoltageYardError):
            _create_circuit(
                service,
                reference_ids,
                voltage_yard_ids,
                actor_user_id,
                terminals=[
                    TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L25"),
                    TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L26"),
                ],
            )

    def test_adding_a_terminal_for_a_voltage_yard_already_on_the_circuit_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(DuplicateTerminalVoltageYardError):
            service.add_terminal(
                circuit.circuit_id,
                voltage_yard_id=voltage_yard_ids["PKLG"],
                breaker_number="L99",
                commissioning_date=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )

    def test_nonexistent_voltage_yard_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(VoltageYardNotFoundError):
            _create_circuit(
                service,
                reference_ids,
                voltage_yard_ids,
                actor_user_id,
                terminals=[
                    TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L25"),
                    TerminalInput(voltage_yard_id=uuid.uuid4(), breaker_number="805"),
                ],
            )

    def test_invalid_voltage_level_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(ReferenceDataNotFoundError):
            service.create_circuit(
                bay_number="Line 1",
                voltage_level_id=99999,
                line_type_id=reference_ids.line_type_id,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                is_interconnector=False,
                remarks=None,
                terminals=_two_terminals(voltage_yard_ids),
                actor_user_id=actor_user_id,
            )

    def test_invalid_line_type_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(ReferenceDataNotFoundError):
            service.create_circuit(
                bay_number="Line 1",
                voltage_level_id=reference_ids.voltage_level_id,
                line_type_id=99999,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                is_interconnector=False,
                remarks=None,
                terminals=_two_terminals(voltage_yard_ids),
                actor_user_id=actor_user_id,
            )

    def test_invalid_initial_status_is_rejected(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(InvalidInitialStatusError):
            _create_circuit(
                service, reference_ids, voltage_yard_ids, actor_user_id, status_code="RETIRED"
            )

    def test_get_nonexistent_circuit_returns_none(self, db_session: Session) -> None:
        service = EquipmentRegistryService(db_session)
        assert service.get_circuit(uuid.uuid4()) is None

    def test_add_terminal_to_nonexistent_circuit_raises_not_found(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        with pytest.raises(NotFoundError):
            service.add_terminal(
                uuid.uuid4(),
                voltage_yard_id=voltage_yard_ids["PKLG"],
                breaker_number="L25",
                commissioning_date=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )


# --- Terminal voltage-level guardrail (Phase 3 UAT follow-up; rule 6a) -------------------
class TestTerminalVoltageLevelGuardrail:
    def test_circuit_create_rejects_a_terminal_voltage_yard_at_a_different_voltage_level(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        mismatched_yard = service.create_voltage_yard(
            substation_id=substation_ids["IGBK"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(TerminalVoltageLevelMismatchError):
            _create_circuit(
                service,
                reference_ids,
                voltage_yard_ids,
                actor_user_id,
                terminals=[
                    TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L1"),
                    TerminalInput(
                        voltage_yard_id=mismatched_yard.voltage_yard_id, breaker_number="L2"
                    ),
                ],
            )

    def test_add_terminal_rejects_a_voltage_yard_at_a_different_voltage_level(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        mismatched_yard = service.create_voltage_yard(
            substation_id=substation_ids["NKST"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(TerminalVoltageLevelMismatchError):
            service.add_terminal(
                circuit.circuit_id,
                voltage_yard_id=mismatched_yard.voltage_yard_id,
                breaker_number="N1",
                commissioning_date=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )

    def test_mismatch_error_message_is_human_readable(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        mismatched_yard = service.create_voltage_yard(
            substation_id=substation_ids["NKST"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(TerminalVoltageLevelMismatchError) as excinfo:
            service.add_terminal(
                circuit.circuit_id,
                voltage_yard_id=mismatched_yard.voltage_yard_id,
                breaker_number="N1",
                commissioning_date=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )
        # UAT regression pattern (DuplicateVoltageYardError, DuplicateVoltageYardError
        # for substation registry): human-readable labels, not raw ids.
        assert "NKST" in str(excinfo.value)
        assert "132kV" in str(excinfo.value)
        assert "500kV" in str(excinfo.value)
        assert str(second_voltage_level_id) not in str(excinfo.value)

    def test_terminals_at_a_non_default_voltage_level_matching_the_circuit_succeed(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """The guardrail rejects a MISMATCH, not any particular voltage
        level — a circuit created entirely at the non-default 132kV level
        succeeds normally."""
        service = EquipmentRegistryService(db_session)
        pklg_yard = service.create_voltage_yard(
            substation_id=substation_ids["PKLG"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        igbk_yard = service.create_voltage_yard(
            substation_id=substation_ids["IGBK"],
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        circuit = service.create_circuit(
            bay_number="Line 2",
            voltage_level_id=second_voltage_level_id,
            line_type_id=reference_ids.line_type_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            is_interconnector=False,
            remarks=None,
            terminals=[
                TerminalInput(voltage_yard_id=pklg_yard.voltage_yard_id, breaker_number="L1"),
                TerminalInput(voltage_yard_id=igbk_yard.voltage_yard_id, breaker_number="L2"),
            ],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        terminals = service.list_terminals(circuit.circuit_id)
        assert {t.voltage_level_label for t in terminals} == {"132kV"}


# --- Search/filter/list behaviour (mandated) ---------------------------------------------
class TestSearchFilterList:
    def test_search_matches_bay_number(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, bay_number="Line 1"
        )
        db_session.commit()

        items, total = service.list_circuits(page=1, page_size=50, search="line 1")
        assert total == 1
        assert items[0].bay_number == "Line 1"

    def test_search_matches_terminal_substation_mnemonic(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        items, total = service.list_circuits(page=1, page_size=50, search="pklg")
        assert total == 1
        assert items[0].terminal_count == 2

    def test_search_with_no_match_returns_empty(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        items, total = service.list_circuits(page=1, page_size=50, search="nonexistent")
        assert total == 0
        assert items == []

    def test_filter_by_voltage_level(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        matching, total = service.list_circuits(
            page=1, page_size=50, voltage_level_id=reference_ids.voltage_level_id
        )
        assert total == 1

        non_matching, total_none = service.list_circuits(
            page=1, page_size=50, voltage_level_id=99999
        )
        assert total_none == 0
        assert non_matching == []

    def test_filter_by_is_interconnector(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, is_interconnector=True
        )
        db_session.commit()

        interconnectors, total = service.list_circuits(page=1, page_size=50, is_interconnector=True)
        assert total == 1
        assert interconnectors[0].is_interconnector is True

        non_interconnectors, total_non = service.list_circuits(
            page=1, page_size=50, is_interconnector=False
        )
        assert total_non == 0

    def test_pagination(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, bay_number="Line 1"
        )
        _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, bay_number="Line 2"
        )
        db_session.commit()

        first_page, total = service.list_circuits(page=1, page_size=1)
        assert total == 2
        assert len(first_page) == 1

        second_page, _ = service.list_circuits(page=2, page_size=1)
        assert len(second_page) == 1
        assert first_page[0].circuit_id != second_page[0].circuit_id


# --- Engineering Connectivity (Substation Detail page) — substation_id filter -------------
# "Which circuits are connected to this substation" — derived from
# Circuit/CircuitTerminal/Substation only, never PSS/E data (Phase 4 will add
# a separate, operational-snapshot connectivity view; this is the
# manually-maintained engineering baseline).
class TestSubstationConnectivityFilter:
    def test_circuit_appears_for_each_of_its_own_terminal_substations(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        pklg_items, pklg_total = service.list_circuits(
            page=1, page_size=50, substation_id=substation_ids["PKLG"]
        )
        assert pklg_total == 1
        assert pklg_items[0].circuit_id == circuit.circuit_id

        igbk_items, igbk_total = service.list_circuits(
            page=1, page_size=50, substation_id=substation_ids["IGBK"]
        )
        assert igbk_total == 1
        assert igbk_items[0].circuit_id == circuit.circuit_id

    def test_unrelated_circuit_does_not_appear(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """The fixture circuit connects PKLG and IGBK only — NKST and ABBA
        (real, otherwise-unrelated substations from the same fixture set)
        must not see it."""
        service = EquipmentRegistryService(db_session)
        _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        nkst_items, nkst_total = service.list_circuits(
            page=1, page_size=50, substation_id=substation_ids["NKST"]
        )
        assert nkst_total == 0
        assert nkst_items == []

        abba_items, abba_total = service.list_circuits(
            page=1, page_size=50, substation_id=substation_ids["ABBA"]
        )
        assert abba_total == 0
        assert abba_items == []

    def test_combines_with_other_filters(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, is_interconnector=True
        )
        db_session.commit()

        matching, total = service.list_circuits(
            page=1,
            page_size=50,
            substation_id=substation_ids["PKLG"],
            is_interconnector=True,
        )
        assert total == 1

        non_matching, total_none = service.list_circuits(
            page=1,
            page_size=50,
            substation_id=substation_ids["PKLG"],
            is_interconnector=False,
        )
        assert total_none == 0
        assert non_matching == []


# --- Full circuit edit (Phase 3 UAT must-fix item 2) --------------------------------------
class TestFullCircuitEdit:
    def test_update_bay_number_writes_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        service.update_circuit(circuit.circuit_id, bay_number="Line 3", actor_user_id=actor_user_id)
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        assert detail.bay_number == "Line 3"
        entries, total = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "bay_number"

    def test_update_line_type_writes_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        cable_line_type_id = (
            db_session.execute(select(LineType).filter_by(code="CABLE"))
            .scalars()
            .one()
            .line_type_id
        )

        service.update_circuit(
            circuit.circuit_id, line_type_id=cable_line_type_id, actor_user_id=actor_user_id
        )
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        assert detail.line_type_id == cable_line_type_id
        entries, _ = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert any(e.field_name == "line_type_id" for e in entries)

    def test_update_voltage_level_writes_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        second_voltage_level_id: int,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        service.update_circuit(
            circuit.circuit_id,
            voltage_level_id=second_voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        assert detail.voltage_level_id == second_voltage_level_id
        entries, _ = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert any(e.field_name == "voltage_level_id" for e in entries)

    def test_status_change_writes_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        service.change_status(
            circuit.circuit_id,
            operational_status_id=reference_ids.status_id_by_code["MOTHBALLED"],
            change_reason="Planned outage",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        assert detail.operational_status_id == reference_ids.status_id_by_code["MOTHBALLED"]

    def test_status_change_to_the_same_status_is_a_no_op(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        service.change_status(
            circuit.circuit_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert total == 0


# --- Per-terminal edit (Phase 3 UAT must-fix items 1 and 2) -------------------------------
class TestTerminalEdit:
    def test_update_breaker_number_writes_audit_row(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        terminal = next(
            t for t in service.list_terminals(circuit.circuit_id) if t.substation_mnemonic == "PKLG"
        )

        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            breaker_number="L99",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        updated = next(
            t for t in service.list_terminals(circuit.circuit_id) if t.substation_mnemonic == "PKLG"
        )
        assert updated.breaker_number == "L99"
        entries, _ = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert any(e.field_name == "terminal_breaker_number" for e in entries)

    def test_set_commissioning_date_on_a_terminal_that_had_none(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        terminal = service.list_terminals(circuit.circuit_id)[0]
        assert terminal.commissioning_date is None

        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            commissioning_date=date(2020, 1, 15),
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        updated = next(
            t
            for t in service.list_terminals(circuit.circuit_id)
            if t.circuit_terminal_id == terminal.circuit_terminal_id
        )
        assert updated.commissioning_date == date(2020, 1, 15)
        entries, _ = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert any(e.field_name == "terminal_commissioning_date" for e in entries)

    def test_commissioning_date_is_optional_and_may_be_cleared(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        terminal = service.list_terminals(circuit.circuit_id)[0]

        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            commissioning_date=date(2020, 1, 15),
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            commissioning_date=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        updated = next(
            t
            for t in service.list_terminals(circuit.circuit_id)
            if t.circuit_terminal_id == terminal.circuit_terminal_id
        )
        assert updated.commissioning_date is None

    def test_update_nonexistent_terminal_raises_not_found(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(NotFoundError):
            service.update_terminal(
                circuit.circuit_id,
                uuid.uuid4(),
                breaker_number="L99",
                actor_user_id=actor_user_id,
            )

    def test_update_terminal_belonging_to_a_different_circuit_raises_not_found(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit_one = _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, bay_number="Line 1"
        )
        # NKST's own default voltage yard (from the shared fixture) is not
        # used by circuit_one (PKLG/IGBK only), so it is free to reuse here.
        circuit_two = _create_circuit(
            service,
            reference_ids,
            voltage_yard_ids,
            actor_user_id,
            bay_number="Line 2",
            terminals=[
                TerminalInput(voltage_yard_id=voltage_yard_ids["ABBA"], breaker_number="A1"),
                TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="N1"),
            ],
        )
        db_session.commit()
        terminal_on_circuit_one = service.list_terminals(circuit_one.circuit_id)[0]

        with pytest.raises(NotFoundError):
            service.update_terminal(
                circuit_two.circuit_id,
                terminal_on_circuit_one.circuit_terminal_id,
                breaker_number="L99",
                actor_user_id=actor_user_id,
            )


# --- Equipment Registry deletion/correction policy (Phase 3 follow-up) -------------------
# No hard delete exists, or will exist, for switchyards/terminals/circuits/
# transformers (CLAUDE.md §11.6). Mistaken records are corrected via a new
# ENTERED_IN_ERROR status, hidden from default views, still reachable for
# audit, with existing references protected.
class TestSwitchyardCorrection:
    def test_new_switchyard_starts_active(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard = service.create_voltage_yard(
            substation_id=substation_ids["PKLG"],
            voltage_level_id=reference_ids.voltage_level_id,
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert yard.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_marking_switchyard_entered_in_error_is_audited(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard_id = voltage_yard_ids["NKST"]  # unused by any circuit/transformer fixture

        service.update_voltage_yard(
            yard_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            change_reason="Wrong voltage level entered",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, total = service.list_voltage_yard_audit_log(yard_id, page=1, page_size=50)
        assert total == 1
        assert entries[0].field_name == "operational_status_id"
        assert entries[0].new_value == "ENTERED_IN_ERROR"
        assert entries[0].change_reason == "Wrong voltage level entered"

    def test_marking_switchyard_entered_in_error_is_blocked_by_an_active_circuit_terminal(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()

        with pytest.raises(SwitchyardHasActiveReferencesError):
            service.update_voltage_yard(
                voltage_yard_ids["PKLG"],
                operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
                actor_user_id=actor_user_id,
            )

    def test_marking_switchyard_entered_in_error_is_blocked_by_an_active_transformer_terminal(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        substation_ids: dict[str, uuid.UUID],
        voltage_yard_ids: dict[str, uuid.UUID],
        lv_voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        service.create_transformer(
            substation_id=substation_ids["PKLG"],
            transformer_number="1",
            hv_switchyard_id=voltage_yard_ids["PKLG"],
            hv_breaker_number="H10",
            lv_switchyard_id=lv_voltage_yard_ids["PKLG"],
            lv_breaker_number="110",
            capacity_mva=None,
            commissioning_date=None,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            transformer_type=None,
            manufacturer=None,
            remarks=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(SwitchyardHasActiveReferencesError):
            service.update_voltage_yard(
                lv_voltage_yard_ids["PKLG"],
                operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
                actor_user_id=actor_user_id,
            )

    def test_switchyard_can_be_corrected_once_no_longer_referenced(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard_id = voltage_yard_ids["NKST"]

        yard = service.update_voltage_yard(
            yard_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert yard.operational_status_id == reference_ids.status_id_by_code["ENTERED_IN_ERROR"]

    def test_entered_in_error_switchyard_excluded_from_default_list_but_reachable_with_flag(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        yard_id = voltage_yard_ids["NKST"]
        service.update_voltage_yard(
            yard_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        default_ids = {y.voltage_yard_id for y in service.list_voltage_yards()}
        assert yard_id not in default_ids

        all_ids = {
            y.voltage_yard_id for y in service.list_voltage_yards(include_entered_in_error=True)
        }
        assert yard_id in all_ids

    def test_new_circuit_terminal_cannot_reference_an_entered_in_error_switchyard(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        service.update_voltage_yard(
            voltage_yard_ids["NKST"],
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(SwitchyardEnteredInErrorError):
            _create_circuit(
                service,
                reference_ids,
                voltage_yard_ids,
                actor_user_id,
                terminals=[
                    TerminalInput(voltage_yard_id=voltage_yard_ids["PKLG"], breaker_number="L1"),
                    TerminalInput(voltage_yard_id=voltage_yard_ids["NKST"], breaker_number="N1"),
                ],
            )

    def test_add_terminal_cannot_reference_an_entered_in_error_switchyard(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        substation_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        service.update_voltage_yard(
            voltage_yard_ids["NKST"],
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(SwitchyardEnteredInErrorError):
            service.add_terminal(
                circuit.circuit_id,
                voltage_yard_id=voltage_yard_ids["NKST"],
                breaker_number="N1",
                commissioning_date=None,
                remarks=None,
                actor_user_id=actor_user_id,
            )


class TestCircuitTerminalCorrection:
    def test_marking_a_terminal_entered_in_error_is_never_blocked(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """CircuitTerminal is a first-class connectivity object that may
        require individual correction — never blocked here even though
        this leaves the circuit with only one active terminal."""
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        terminal = service.list_terminals(circuit.circuit_id)[0]

        updated = service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert updated.operational_status_id == reference_ids.status_id_by_code["ENTERED_IN_ERROR"]

    def test_marking_a_terminal_entered_in_error_is_audited(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        terminal = service.list_terminals(circuit.circuit_id)[0]

        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        entries, _ = service.list_audit_log(circuit.circuit_id, page=1, page_size=50)
        assert any(e.field_name == "terminal_status" for e in entries)

    def test_circuit_name_and_terminal_count_exclude_entered_in_error_terminals_in_list_view(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        pklg_terminal = next(
            t for t in service.list_terminals(circuit.circuit_id) if t.substation_mnemonic == "PKLG"
        )

        service.update_terminal(
            circuit.circuit_id,
            pklg_terminal.circuit_terminal_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        items, _ = service.list_circuits(page=1, page_size=50)
        summary = next(c for c in items if c.circuit_id == circuit.circuit_id)
        assert summary.terminal_count == 1
        assert "PKLG" not in summary.circuit_name
        assert summary.circuit_name == "IGBK"

    def test_get_circuit_detail_still_shows_entered_in_error_terminal_but_name_excludes_it(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """The detail page is this module's own audit/history view — every
        terminal remains visible there regardless of status."""
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        pklg_terminal = next(
            t for t in service.list_terminals(circuit.circuit_id) if t.substation_mnemonic == "PKLG"
        )

        service.update_terminal(
            circuit.circuit_id,
            pklg_terminal.circuit_terminal_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        detail = service.get_circuit(circuit.circuit_id)
        assert detail is not None
        assert len(detail.terminals) == 2  # still both, for audit purposes
        assert detail.circuit_name == "IGBK"  # but the computed name excludes the corrected one


class TestCircuitActivationGuard:
    def test_cannot_activate_circuit_with_fewer_than_two_active_terminals(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, status_code="PLANNED"
        )
        db_session.commit()
        terminal = service.list_terminals(circuit.circuit_id)[0]
        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        with pytest.raises(InsufficientActiveTerminalsForActivationError):
            service.change_status(
                circuit.circuit_id,
                operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
                change_reason=None,
                actor_user_id=actor_user_id,
            )

    def test_can_activate_circuit_with_two_active_terminals(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(
            service, reference_ids, voltage_yard_ids, actor_user_id, status_code="PLANNED"
        )
        db_session.commit()

        updated = service.change_status(
            circuit.circuit_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()
        assert updated.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]

    def test_reaffirming_an_already_active_circuit_is_a_noop_even_if_now_incomplete(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        """A circuit may be temporarily incomplete while its terminals are
        corrected — change_status's own idempotent no-op path (setting the
        same status it already has) is not retroactively blocked by the
        activation guard, since no real transition is happening."""
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        terminal = service.list_terminals(circuit.circuit_id)[0]
        service.update_terminal(
            circuit.circuit_id,
            terminal.circuit_terminal_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        # No exception: circuit is already ACTIVE, so this is a no-op.
        result = service.change_status(
            circuit.circuit_id,
            operational_status_id=reference_ids.status_id_by_code["ACTIVE"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        assert result.operational_status_id == reference_ids.status_id_by_code["ACTIVE"]


class TestEnteredInErrorListFiltering:
    def test_entered_in_error_circuit_excluded_from_default_list_but_reachable_by_id(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        service.change_status(
            circuit.circuit_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            change_reason="Duplicate entry",
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        default_items, default_total = service.list_circuits(page=1, page_size=50)
        assert circuit.circuit_id not in {c.circuit_id for c in default_items}
        assert default_total == 0

        all_items, all_total = service.list_circuits(
            page=1, page_size=50, include_entered_in_error=True
        )
        assert circuit.circuit_id in {c.circuit_id for c in all_items}
        assert all_total == 1

        # Still directly reachable — the detail page is this module's own
        # audit/history view.
        assert service.get_circuit(circuit.circuit_id) is not None

    def test_explicit_operational_status_id_filter_bypasses_default_exclusion(
        self,
        db_session: Session,
        reference_ids: ReferenceIds,
        voltage_yard_ids: dict[str, uuid.UUID],
        actor_user_id: uuid.UUID,
    ) -> None:
        service = EquipmentRegistryService(db_session)
        circuit = _create_circuit(service, reference_ids, voltage_yard_ids, actor_user_id)
        db_session.commit()
        service.change_status(
            circuit.circuit_id,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
            change_reason=None,
            actor_user_id=actor_user_id,
        )
        db_session.commit()

        items, total = service.list_circuits(
            page=1,
            page_size=50,
            operational_status_id=reference_ids.status_id_by_code["ENTERED_IN_ERROR"],
        )
        assert total == 1
        assert items[0].circuit_id == circuit.circuit_id
