"""Automatic Load Shedding Functionality Registry service layer
(CLAUDE.md §14) — business rules, transactions, orchestration, and audit
writing live here, and only here (CLAUDE.md A1: this module's own tables
are written to exclusively by this layer).

Cross-module reads go through `EquipmentRegistryService`'s own public
methods (CLAUDE.md A1) — never this module's repository reaching into
Equipment Registry's tables directly, and never a cross-module SQL join.

Lifecycle (Status Model Refinement — engineering refinement, superseding
the earlier `ACTIVE <-> INACTIVE -> DECOMMISSIONED` design):

    ACTIVE -> DECOMMISSIONED (terminal)

The *persisted* `lifecycle_status` column is now binary: a record is
created directly into `ACTIVE` (there is no other legal creation-time
value) and may only ever transition once, to `DECOMMISSIONED` — a terminal,
one-way, reasoned, audited engineering decision. There is no longer a
manually-toggled "temporarily unavailable" state, and consequently no
`activate`/`deactivate` operation any more.

Status computation (the three-value status an engineer actually sees on
the registry page — Available / Assigned / Decommissioned) is a *separate*
concept from `lifecycle_status`, computed here at read time, never stored:

    DECOMMISSIONED  <=>  lifecycle_status == "DECOMMISSIONED"
    ASSIGNED        <=>  lifecycle_status == "ACTIVE" and the terminal is in
                         the caller-supplied `assigned_terminal_ids` set
    AVAILABLE       <=>  lifecycle_status == "ACTIVE" and the terminal is
                         not in that set

`assigned_terminal_ids` is the Future Integration Contract this module
exposes for UFLS/UVLS: every read method that returns a display `status`
accepts an optional `assigned_terminal_ids: set[uuid.UUID] | None` — the
union of every Bay Terminal ID currently referenced by an *Active* UFLS or
UVLS scheme version, scheme-type-agnostic (module document: "referenced by
at least one active UFLS and/or UVLS scheme"). This module never queries
UFLS/UVLS's own tables to build that set itself (CLAUDE.md A1) — a future
scheme module (or a future composition layer) supplies it, in-process, as
a plain parameter. No caller exists yet, so every read defaults to an
empty set, and every non-decommissioned record therefore displays as
Available — exactly the "Current Phase Behaviour" the module document
requires, with no placeholder assignment table anywhere in this module.

Bay Terminal identity displayed to engineers (`bay_label`, on every read
DTO) is composed here from Equipment Registry's own already-computed
identity — `Circuit.circuit_name`/`bay_number` and `Transformer.
generated_short_name` — via `EquipmentRegistryService.
get_circuit_terminal_identity`/`get_transformer_terminal_identity`, never
re-derived or duplicated as stored data (module document §4).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

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
from app.modules.automatic_load_shedding_functionality.models import (
    AutomaticLoadSheddingFunctionality,
    AutomaticLoadSheddingFunctionalityAuditLog,
)
from app.modules.automatic_load_shedding_functionality.repository import (
    AutomaticLoadSheddingFunctionalityRepository,
)
from app.modules.automatic_load_shedding_functionality.schemas import (
    AssignmentAwareCandidateList,
    CandidateTerminal,
    FunctionalityAuditLogEntry,
    FunctionalityDetail,
    FunctionalitySummary,
)
from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService


def _compute_display_status(
    *, lifecycle_status: str, terminal_id: uuid.UUID, assigned_terminal_ids: set[uuid.UUID]
) -> str:
    """Available / Assigned / Decommissioned — see module docstring. Pure
    function of already-known values; never itself reads the database or
    queries another module."""
    if lifecycle_status == "DECOMMISSIONED":
        return "DECOMMISSIONED"
    if terminal_id in assigned_terminal_ids:
        return "ASSIGNED"
    return "AVAILABLE"


@dataclass
class _TerminalContext:
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_id: int
    voltage_level_label: str
    bay_label: str


class AutomaticLoadSheddingFunctionalityService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = AutomaticLoadSheddingFunctionalityRepository(db)
        # Cross-module reads only, via the owning module's own service
        # layer (CLAUDE.md A1) — never this module's repository reaching
        # into Equipment Registry's tables.
        self.equipment_registry = EquipmentRegistryService(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _audit(
        self,
        *,
        functionality_id: uuid.UUID,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            AutomaticLoadSheddingFunctionalityAuditLog(
                functionality_id=functionality_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _resolve_user(self, user_id: uuid.UUID | None) -> UserSummary | None:
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    @staticmethod
    def _terminal_id(functionality: AutomaticLoadSheddingFunctionality) -> uuid.UUID:
        terminal_id = functionality.circuit_terminal_id or functionality.transformer_terminal_id
        assert terminal_id is not None
        return terminal_id

    def _resolve_target_context(
        self, functionality: AutomaticLoadSheddingFunctionality
    ) -> _TerminalContext | None:
        """Read-only composition against Equipment Registry — never stored
        here (module document §4). Returns `None` for an orphaned
        reference (the terminal was since deleted/re-typed in Equipment
        Registry) rather than raising — module document §10's "unknown,
        not invalid" tolerance.

        `bay_label` is the full engineering bay identity (never just a
        breaker number) — "Line {circuit name} {bay number}" for a Circuit
        Terminal, "Transformer {generated short name}" for a Transformer
        Terminal — reusing Equipment Registry's own already-computed
        `circuit_name`/`generated_short_name` (via `get_circuit_terminal_
        identity`/`get_transformer_terminal_identity`) so two terminals at
        the same substation and voltage level are always displayed
        distinctly (e.g. "Line IGBK–ROMEO No.1" vs "No.2"; "Transformer T1"
        vs "Transformer T2"). Substation and voltage level are reported
        separately (`substation_mnemonic`/`voltage_level_label`) so callers
        can compose the full "Substation | Voltage | Bay" identity
        consistently across every view (list, detail, candidate, create
        picker) without this module ever storing that composed string."""
        if functionality.target_type == "CIRCUIT_TERMINAL":
            assert functionality.circuit_terminal_id is not None
            identity = self.equipment_registry.get_circuit_terminal_identity(
                functionality.circuit_terminal_id
            )
            if identity is None:
                return None
            return _TerminalContext(
                substation_id=identity.substation_id,
                substation_mnemonic=identity.substation_mnemonic,
                substation_official_name=identity.substation_official_name,
                voltage_level_id=identity.voltage_level_id,
                voltage_level_label=identity.voltage_level_label,
                bay_label=f"Line {identity.circuit_name} {identity.bay_number}",
            )

        assert functionality.transformer_terminal_id is not None
        transformer_identity = self.equipment_registry.get_transformer_terminal_identity(
            functionality.transformer_terminal_id
        )
        if transformer_identity is None:
            return None
        return _TerminalContext(
            substation_id=transformer_identity.substation_id,
            substation_mnemonic=transformer_identity.substation_mnemonic,
            substation_official_name=transformer_identity.substation_official_name,
            voltage_level_id=transformer_identity.voltage_level_id,
            voltage_level_label=transformer_identity.voltage_level_label,
            bay_label=f"Transformer {transformer_identity.generated_short_name}",
        )

    def _require_terminal_exists(
        self,
        *,
        target_type: str,
        circuit_terminal_id: uuid.UUID | None,
        transformer_terminal_id: uuid.UUID | None,
    ) -> None:
        if target_type == "CIRCUIT_TERMINAL":
            if circuit_terminal_id is None or transformer_terminal_id is not None:
                raise ValidationAppError(
                    "target_type=CIRCUIT_TERMINAL requires circuit_terminal_id only "
                    "(automatic-load-shedding-functionality-registry-module.md §9 rule 1)."
                )
            if self.equipment_registry.get_circuit_terminal_summary(circuit_terminal_id) is None:
                raise CircuitTerminalNotFoundError(circuit_terminal_id)
        else:
            if transformer_terminal_id is None or circuit_terminal_id is not None:
                raise ValidationAppError(
                    "target_type=TRANSFORMER_TERMINAL requires transformer_terminal_id only "
                    "(automatic-load-shedding-functionality-registry-module.md §9 rule 1)."
                )
            if (
                self.equipment_registry.get_transformer_terminal_summary(transformer_terminal_id)
                is None
            ):
                raise TransformerTerminalNotFoundError(transformer_terminal_id)

    # --- Create -----------------------------------------------------------------
    def create(
        self,
        *,
        target_type: str,
        circuit_terminal_id: uuid.UUID | None,
        transformer_terminal_id: uuid.UUID | None,
        ufls_function: bool,
        uvls_function: bool,
        relay_make: str | None,
        relay_model: str | None,
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> AutomaticLoadSheddingFunctionality:
        self._require_terminal_exists(
            target_type=target_type,
            circuit_terminal_id=circuit_terminal_id,
            transformer_terminal_id=transformer_terminal_id,
        )
        if not (ufls_function or uvls_function):
            raise NoFunctionAssignedError()

        if target_type == "CIRCUIT_TERMINAL":
            existing = self.repo.get_active_by_circuit_terminal(circuit_terminal_id)  # type: ignore[arg-type]
        else:
            existing = self.repo.get_active_by_transformer_terminal(transformer_terminal_id)  # type: ignore[arg-type]
        if existing is not None:
            terminal_id = (
                circuit_terminal_id
                if target_type == "CIRCUIT_TERMINAL"
                else transformer_terminal_id
            )
            raise TerminalAlreadyHasFunctionalityError(target_type, terminal_id)

        # Always created ACTIVE (Available, once displayed) — Status Model
        # Refinement §1: there is no other legal creation-time lifecycle
        # value any more.
        functionality = self.repo.add(
            AutomaticLoadSheddingFunctionality(
                id=uuid.uuid4(),
                target_type=target_type,
                circuit_terminal_id=circuit_terminal_id,
                transformer_terminal_id=transformer_terminal_id,
                ufls_function=ufls_function,
                uvls_function=uvls_function,
                lifecycle_status="ACTIVE",
                relay_make=relay_make,
                relay_model=relay_model,
                remarks=remarks,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        # Module document §14 explicitly lists "created" as a mandatory
        # audit event for this module — unlike Substation Registry's own
        # choice to rely on created_by/created_at alone, this module's own
        # approved architecture calls it out by name.
        self._audit(
            functionality_id=functionality.id,
            field_name="lifecycle_status",
            old_value=None,
            new_value="ACTIVE",
            actor_user_id=actor_user_id,
        )
        return functionality

    # --- Update (metadata only — excludes status, see decommission below) -------
    def update_metadata(
        self,
        functionality_id: uuid.UUID,
        *,
        ufls_function: bool | None = None,
        uvls_function: bool | None = None,
        relay_make: str | None = ...,  # type: ignore[assignment]
        relay_model: str | None = ...,  # type: ignore[assignment]
        remarks: str | None = ...,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> AutomaticLoadSheddingFunctionality:
        functionality = self.repo.get_by_id(functionality_id)
        if functionality is None:
            raise FunctionalityNotFoundError(functionality_id)
        if functionality.lifecycle_status == "DECOMMISSIONED":
            raise FunctionalityDecommissionedImmutableError(functionality_id)

        changed = False

        if ufls_function is not None and ufls_function != functionality.ufls_function:
            new_ufls = ufls_function
            new_uvls = uvls_function if uvls_function is not None else functionality.uvls_function
            if not (new_ufls or new_uvls):
                raise NoFunctionAssignedError()
            self._audit(
                functionality_id=functionality_id,
                field_name="ufls_function",
                old_value=functionality.ufls_function,
                new_value=ufls_function,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            functionality.ufls_function = ufls_function
            changed = True

        if uvls_function is not None and uvls_function != functionality.uvls_function:
            if not (functionality.ufls_function or uvls_function):
                raise NoFunctionAssignedError()
            self._audit(
                functionality_id=functionality_id,
                field_name="uvls_function",
                old_value=functionality.uvls_function,
                new_value=uvls_function,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            functionality.uvls_function = uvls_function
            changed = True

        if relay_make is not ... and relay_make != functionality.relay_make:
            self._audit(
                functionality_id=functionality_id,
                field_name="relay_make",
                old_value=functionality.relay_make,
                new_value=relay_make,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            functionality.relay_make = relay_make
            changed = True

        if relay_model is not ... and relay_model != functionality.relay_model:
            self._audit(
                functionality_id=functionality_id,
                field_name="relay_model",
                old_value=functionality.relay_model,
                new_value=relay_model,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            functionality.relay_model = relay_model
            changed = True

        if remarks is not ... and remarks != functionality.remarks:
            self._audit(
                functionality_id=functionality_id,
                field_name="remarks",
                old_value=functionality.remarks,
                new_value=remarks,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            functionality.remarks = remarks
            changed = True

        if changed:
            functionality.updated_by_user_id = actor_user_id
            self.db.flush()

        return functionality

    # --- Lifecycle: decommission (the only remaining transition) ----------------
    def decommission(
        self, functionality_id: uuid.UUID, *, change_reason: str | None, actor_user_id: uuid.UUID
    ) -> AutomaticLoadSheddingFunctionality:
        """Terminal, one-way transition — the only lifecycle action this
        module still exposes (Status Model Refinement §8). A record already
        `DECOMMISSIONED` can never be decommissioned again (or otherwise
        edited) — `FunctionalityDecommissionedImmutableError`, not a
        silent no-op, since re-applying this action to an already-terminal
        record would misrepresent an immutable historical fact."""
        functionality = self.repo.get_by_id(functionality_id)
        if functionality is None:
            raise FunctionalityNotFoundError(functionality_id)
        if functionality.lifecycle_status == "DECOMMISSIONED":
            raise FunctionalityDecommissionedImmutableError(functionality_id)
        if not change_reason:
            raise DecommissionReasonRequiredError()

        self._audit(
            functionality_id=functionality_id,
            field_name="lifecycle_status",
            old_value="ACTIVE",
            new_value="DECOMMISSIONED",
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        functionality.lifecycle_status = "DECOMMISSIONED"
        functionality.updated_by_user_id = actor_user_id
        self.db.flush()
        return functionality

    # --- Read ---------------------------------------------------------------------
    def _to_summary(
        self,
        functionality: AutomaticLoadSheddingFunctionality,
        context: _TerminalContext | None,
        display_status: str,
    ) -> FunctionalitySummary:
        return FunctionalitySummary(
            id=functionality.id,
            target_type=functionality.target_type,
            circuit_terminal_id=functionality.circuit_terminal_id,
            transformer_terminal_id=functionality.transformer_terminal_id,
            substation_id=context.substation_id if context else uuid.UUID(int=0),
            substation_mnemonic=context.substation_mnemonic if context else "",
            voltage_level_label=context.voltage_level_label if context else "",
            bay_label=context.bay_label if context else "",
            ufls_function=functionality.ufls_function,
            uvls_function=functionality.uvls_function,
            status=display_status,
            updated_at=functionality.updated_at,
        )

    def get_detail(
        self,
        functionality_id: uuid.UUID,
        *,
        assigned_terminal_ids: set[uuid.UUID] | None = None,
    ) -> FunctionalityDetail | None:
        """`assigned_terminal_ids` — Future Integration Contract (module
        docstring): defaults to empty (today's "UFLS/UVLS do not exist
        yet" phase, module document's Current Phase Behaviour), but a
        future caller may supply the real current-Active-scheme-assignment
        set here, in-process, without this module ever querying UFLS/UVLS's
        own tables (CLAUDE.md A1)."""
        functionality = self.repo.get_by_id(functionality_id)
        if functionality is None:
            return None
        assigned_terminal_ids = assigned_terminal_ids or set()
        context = self._resolve_target_context(functionality)
        display_status = _compute_display_status(
            lifecycle_status=functionality.lifecycle_status,
            terminal_id=self._terminal_id(functionality),
            assigned_terminal_ids=assigned_terminal_ids,
        )
        return FunctionalityDetail(
            id=functionality.id,
            target_type=functionality.target_type,
            circuit_terminal_id=functionality.circuit_terminal_id,
            transformer_terminal_id=functionality.transformer_terminal_id,
            substation_id=context.substation_id if context else uuid.UUID(int=0),
            substation_mnemonic=context.substation_mnemonic if context else "",
            substation_official_name=context.substation_official_name if context else "",
            voltage_level_label=context.voltage_level_label if context else "",
            bay_label=context.bay_label if context else "",
            ufls_function=functionality.ufls_function,
            uvls_function=functionality.uvls_function,
            status=display_status,
            relay_make=functionality.relay_make,
            relay_model=functionality.relay_model,
            remarks=functionality.remarks,
            created_at=functionality.created_at,
            updated_at=functionality.updated_at,
            created_by=self._resolve_user(functionality.created_by_user_id),
            updated_by=self._resolve_user(functionality.updated_by_user_id),
        )

    def list_functionality(
        self,
        *,
        page: int,
        page_size: int,
        target_type: str | None = None,
        ufls_function: bool | None = None,
        uvls_function: bool | None = None,
        status: str | None = None,
        substation_id: uuid.UUID | None = None,
        voltage_level_id: int | None = None,
        assigned_terminal_ids: set[uuid.UUID] | None = None,
    ) -> tuple[list[FunctionalitySummary], int]:
        """Own-column filters (`target_type`/`ufls_function`/`uvls_function`)
        apply at the repository level; `substation_id`/`voltage_level_id`
        (attributes this module does not store) and `status` (a computed
        display value — AVAILABLE/ASSIGNED/DECOMMISSIONED — never a raw
        column) apply here, in Python, after resolving each row's terminal
        context and display status. See `repository.py`'s own docstring
        for why substation/voltage filtering is Python-side; `status` joins
        them for the same reason: it cannot be evaluated until each row's
        assignment state is known. `assigned_terminal_ids` — see
        `get_detail`'s own docstring; same Future Integration Contract."""
        assigned_terminal_ids = assigned_terminal_ids or set()
        rows = self.repo.list_all(
            target_type=target_type,
            ufls_function=ufls_function,
            uvls_function=uvls_function,
        )

        enriched: list[FunctionalitySummary] = []
        for functionality in rows:
            context = self._resolve_target_context(functionality)
            if context is None:
                # Orphaned reference — omitted from output, never raised
                # (module document §10, §16).
                continue
            if substation_id is not None and context.substation_id != substation_id:
                continue
            if voltage_level_id is not None and context.voltage_level_id != voltage_level_id:
                continue
            display_status = _compute_display_status(
                lifecycle_status=functionality.lifecycle_status,
                terminal_id=self._terminal_id(functionality),
                assigned_terminal_ids=assigned_terminal_ids,
            )
            if status is not None and display_status != status:
                continue
            enriched.append(self._to_summary(functionality, context, display_status))

        total = len(enriched)
        offset = (page - 1) * page_size
        return enriched[offset : offset + page_size], total

    def list_audit_log(
        self, functionality_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[FunctionalityAuditLogEntry], int]:
        items, total = self.repo.list_audit_log(
            functionality_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            FunctionalityAuditLogEntry(
                log_id=e.log_id,
                field_name=e.field_name,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total

    # --- Service interfaces for future UFLS/UVLS use (module document §13) ------
    def is_ufls_capable(
        self,
        *,
        circuit_terminal_id: uuid.UUID | None = None,
        transformer_terminal_id: uuid.UUID | None = None,
    ) -> bool:
        record = self._get_active_record(
            circuit_terminal_id=circuit_terminal_id, transformer_terminal_id=transformer_terminal_id
        )
        return (
            record is not None
            and record.lifecycle_status == "ACTIVE"
            and record.ufls_function
        )

    def is_uvls_capable(
        self,
        *,
        circuit_terminal_id: uuid.UUID | None = None,
        transformer_terminal_id: uuid.UUID | None = None,
    ) -> bool:
        record = self._get_active_record(
            circuit_terminal_id=circuit_terminal_id, transformer_terminal_id=transformer_terminal_id
        )
        return (
            record is not None
            and record.lifecycle_status == "ACTIVE"
            and record.uvls_function
        )

    def _get_active_record(
        self,
        *,
        circuit_terminal_id: uuid.UUID | None,
        transformer_terminal_id: uuid.UUID | None,
    ) -> AutomaticLoadSheddingFunctionality | None:
        if circuit_terminal_id is not None:
            return self.repo.get_active_by_circuit_terminal(circuit_terminal_id)
        if transformer_terminal_id is not None:
            return self.repo.get_active_by_transformer_terminal(transformer_terminal_id)
        return None

    def list_candidate_terminals(
        self,
        *,
        scheme_type: str,
        substation_id: uuid.UUID | None = None,
        target_type: str | None = None,
        voltage_level_id: int | None = None,
    ) -> list[CandidateTerminal]:
        """Module document §13 — every functionally-ready (non-
        decommissioned) record matching the requested scheme type's
        function flag. Does not know about scheme assignments (module
        document §4, §9 rule 7) — returns *all* functionally-ready bays,
        Available or Assigned alike; see `list_assigned_and_available`
        below for the composition point that partitions this by assignment
        once a caller can supply that set.

        `scheme_type` must be `UFLS` or `UVLS` — EMLS is deliberately never
        accepted (module document §4, §9 rule 4): EMLS has no automatic-
        functionality prerequisite, so a candidate search "for EMLS" is a
        category error, not an empty result. The API layer's `SchemeType`
        Literal already rejects this at the request-validation boundary;
        this check guards direct, in-process service callers too (a future
        UFLS/UVLS module calling this method in-process, not via HTTP)."""
        if scheme_type not in ("UFLS", "UVLS"):
            raise ValidationAppError(
                f"Unsupported scheme_type '{scheme_type}' — this registry only recognizes UFLS "
                "and UVLS (EMLS has no automatic-functionality prerequisite, module document §4)."
            )
        ufls_filter = True if scheme_type == "UFLS" else None
        uvls_filter = True if scheme_type == "UVLS" else None
        rows = self.repo.list_all(
            target_type=target_type,
            ufls_function=ufls_filter,
            uvls_function=uvls_filter,
            lifecycle_status="ACTIVE",
        )

        candidates: list[CandidateTerminal] = []
        for functionality in rows:
            context = self._resolve_target_context(functionality)
            if context is None:
                continue
            if substation_id is not None and context.substation_id != substation_id:
                continue
            if voltage_level_id is not None and context.voltage_level_id != voltage_level_id:
                continue
            candidates.append(
                CandidateTerminal(
                    id=functionality.id,
                    target_type=functionality.target_type,
                    circuit_terminal_id=functionality.circuit_terminal_id,
                    transformer_terminal_id=functionality.transformer_terminal_id,
                    substation_id=context.substation_id,
                    substation_mnemonic=context.substation_mnemonic,
                    voltage_level_label=context.voltage_level_label,
                    bay_label=context.bay_label,
                    ufls_function=functionality.ufls_function,
                    uvls_function=functionality.uvls_function,
                )
            )
        return candidates

    def list_assigned_and_available(
        self,
        *,
        scheme_type: str,
        assigned_terminal_ids: set[uuid.UUID],
        substation_id: uuid.UUID | None = None,
        target_type: str | None = None,
        voltage_level_id: int | None = None,
    ) -> AssignmentAwareCandidateList:
        """Module document §13 — a convenience composition, callable once
        UFLS/UVLS exist. `assigned_terminal_ids` is supplied by the
        *caller* (the scheme module's own current-Active-version
        assignment set) — this module never queries another module's
        tables itself (CLAUDE.md A1). This is the same Future Integration
        Contract `get_detail`/`list_functionality` use for the registry's
        own Available/Assigned status display."""
        candidates = self.list_candidate_terminals(
            scheme_type=scheme_type,
            substation_id=substation_id,
            target_type=target_type,
            voltage_level_id=voltage_level_id,
        )
        assigned: list[CandidateTerminal] = []
        available: list[CandidateTerminal] = []
        for candidate in candidates:
            terminal_id = candidate.circuit_terminal_id or candidate.transformer_terminal_id
            if terminal_id in assigned_terminal_ids:
                assigned.append(candidate)
            else:
                available.append(candidate)
        return AssignmentAwareCandidateList(assigned=assigned, available=available)
