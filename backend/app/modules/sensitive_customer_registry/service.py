"""Sensitive Customer Registry service layer (CLAUDE.md §14) — business
rules, transactions, orchestration, and audit writing live here, and only
here (CLAUDE.md A1: this module's own tables are written to exclusively by
this layer).

Cross-module reads go through `EquipmentRegistryService`'s own public
methods (CLAUDE.md A1) — never this module's repository reaching into
Equipment Registry's tables directly, and never a cross-module SQL join.
This module never calls, and is never called by, Network Model, the
Automatic Load Shedding Functionality Registry, Critical Infrastructure, or
any scheme module (ADR-012 Service Interface Expectations; module document
§13) — the only cross-module dependency is Equipment Registry (Transformer
Terminal existence/identity) and IAM (audit attribution, permissions).

Lifecycle (module document §8; implementation spec §7):

    ACTIVE <-> ARCHIVED (reversible, both directions reasoned and audited)
    ACTIVE -> ENTERED_IN_ERROR (terminal)
    ARCHIVED -> ENTERED_IN_ERROR (terminal)
    ENTERED_IN_ERROR -> * (prohibited, no exceptions)

Every transition requires a non-empty `change_reason` — stricter than
ALSF's own optional-reason-except-for-decommission rule, since even a
reversible Active<->Archived transition here represents a real engineering
judgment about a facility's current sensitivity (module document §10).

Correction 4, generalised by ADR-013 (stale Transformer Terminal
handling): a facility is **never** omitted from any read because an
associated terminal cannot currently be resolved through Equipment
Registry. Every summary/detail response instead reports, per association,
a `resolution` (`RESOLVED`/`UNRESOLVED`) independent of
`lifecycle_status`, plus a facility-level `transformer_terminal_resolution`
aggregate (`NOT_ASSIGNED`/`RESOLVED`/`UNRESOLVED`) for list filtering only
— see `_resolve_context` and `_build_terminal_associations` below.

Correction 5, generalised by ADR-013 decision 3 (association-change
auditing): adding or removing a Transformer Terminal association via
`set_terminal_associations` requires a non-empty `change_reason` whenever
the set actually changes, enforced here, not merely recommended. One
audit row is written per actual addition or removal — never one opaque
bulk "set changed" event.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.modules.sensitive_customer_registry.exceptions import (
    FacilityEnteredInErrorImmutableError,
    FacilitySectorInactiveError,
    FacilitySectorNotFoundError,
    InvalidLifecycleTransitionError,
    LifecycleReasonRequiredError,
    ReassignmentReasonRequiredError,
    ReferenceDataNotSeededError,
    SensitiveFacilityNotFoundError,
    SensitivityClassificationInactiveError,
    SensitivityClassificationNotFoundError,
    TransformerTerminalNotFoundError,
    ValidationAppError,
)
from app.modules.sensitive_customer_registry.models import (
    FacilitySector,
    SensitiveCustomerRegistryAuditLog,
    SensitiveFacility,
    SensitiveFacilityTransformerTerminal,
    SensitivityClassification,
)
from app.modules.sensitive_customer_registry.repository import (
    SensitiveCustomerRegistryRepository,
)
from app.modules.sensitive_customer_registry.schemas import (
    FacilitySectorSummary,
    SensitiveFacilityAuditLogEntry,
    SensitiveFacilityDetail,
    SensitiveFacilitySummary,
    SensitiveFacilitySummaryCounts,
    SensitiveFacilityTerminalAssociation,
    SensitivityClassificationSummary,
)

# Module document §8 — the only legal transitions. `ENTERED_IN_ERROR` has no
# outgoing edge at all (terminal, no exceptions).
_ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    ("ACTIVE", "ARCHIVED"),
    ("ARCHIVED", "ACTIVE"),
    ("ACTIVE", "ENTERED_IN_ERROR"),
    ("ARCHIVED", "ENTERED_IN_ERROR"),
}

_UNSET = object()


@dataclass
class _TerminalContext:
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_label: str
    bay_label: str
    side: str


class SensitiveCustomerRegistryService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SensitiveCustomerRegistryRepository(db)
        # Cross-module reads only, via the owning module's own service
        # layer (CLAUDE.md A1) — never this module's repository reaching
        # into Equipment Registry's tables.
        self.equipment_registry = EquipmentRegistryService(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _audit_facility(
        self,
        *,
        facility_id: uuid.UUID,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            SensitiveCustomerRegistryAuditLog(
                subject_type="SENSITIVE_FACILITY",
                sensitive_facility_id=facility_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _audit_sector(
        self,
        *,
        facility_sector_id: int,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            SensitiveCustomerRegistryAuditLog(
                subject_type="FACILITY_SECTOR",
                facility_sector_id=facility_sector_id,
                field_name=field_name,
                old_value=None if old_value is None else str(old_value),
                new_value=None if new_value is None else str(new_value),
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _audit_classification(
        self,
        *,
        sensitivity_classification_id: int,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            SensitiveCustomerRegistryAuditLog(
                subject_type="SENSITIVITY_CLASSIFICATION",
                sensitivity_classification_id=sensitivity_classification_id,
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

    def _resolve_context(
        self, transformer_terminal_id: uuid.UUID | None
    ) -> tuple[str, _TerminalContext | None]:
        """Correction 4 — returns (resolution, context) for one terminal
        id. `NOT_ASSIGNED` if no terminal is given; `UNRESOLVED` (never an
        exception, never a dropped row) if Equipment Registry cannot
        currently resolve it; `RESOLVED` otherwise. Since ADR-013, called
        once per association, never once per facility."""
        if transformer_terminal_id is None:
            return "NOT_ASSIGNED", None
        identity = self.equipment_registry.get_transformer_terminal_identity(
            transformer_terminal_id
        )
        if identity is None:
            return "UNRESOLVED", None
        return "RESOLVED", _TerminalContext(
            substation_id=identity.substation_id,
            substation_mnemonic=identity.substation_mnemonic,
            substation_official_name=identity.substation_official_name,
            voltage_level_label=identity.voltage_level_label,
            bay_label=f"Transformer {identity.generated_short_name}",
            side=identity.side,
        )

    def _build_terminal_associations(
        self, associations: list[SensitiveFacilityTransformerTerminal]
    ) -> tuple[list[SensitiveFacilityTerminalAssociation], str]:
        """Builds the full per-association detail list plus the
        facility-level aggregate resolution (ADR-013 decision 4):
        `NOT_ASSIGNED` if there are no associations, `RESOLVED` if every
        association resolves, `UNRESOLVED` if at least one does not."""
        result: list[SensitiveFacilityTerminalAssociation] = []
        any_unresolved = False
        for association in associations:
            resolution, context = self._resolve_context(association.transformer_terminal_id)
            if resolution == "UNRESOLVED":
                any_unresolved = True
            result.append(
                SensitiveFacilityTerminalAssociation(
                    transformer_terminal_id=association.transformer_terminal_id,
                    resolution=resolution,  # type: ignore[arg-type]
                    substation_id=context.substation_id if context else None,
                    substation_mnemonic=context.substation_mnemonic if context else None,
                    substation_official_name=(
                        context.substation_official_name if context else None
                    ),
                    voltage_level_label=context.voltage_level_label if context else None,
                    bay_label=context.bay_label if context else None,
                    side=context.side if context else None,
                )
            )
        if not associations:
            aggregate = "NOT_ASSIGNED"
        elif any_unresolved:
            aggregate = "UNRESOLVED"
        else:
            aggregate = "RESOLVED"
        return result, aggregate

    def _require_terminal_exists(self, transformer_terminal_id: uuid.UUID) -> None:
        summary = self.equipment_registry.get_transformer_terminal_summary(transformer_terminal_id)
        if summary is None:
            raise TransformerTerminalNotFoundError(transformer_terminal_id)

    def _require_sector(self, facility_sector_id: int) -> FacilitySector:
        sector = self.repo.get_facility_sector_by_id(facility_sector_id)
        if sector is None:
            raise FacilitySectorNotFoundError(facility_sector_id)
        if not sector.is_active:
            raise FacilitySectorInactiveError(facility_sector_id)
        return sector

    def _require_classification(
        self, sensitivity_classification_id: int
    ) -> SensitivityClassification:
        classification = self.repo.get_sensitivity_classification_by_id(
            sensitivity_classification_id
        )
        if classification is None:
            raise SensitivityClassificationNotFoundError(sensitivity_classification_id)
        if not classification.is_active:
            raise SensitivityClassificationInactiveError(sensitivity_classification_id)
        return classification

    def _get_editable_facility(self, facility_id: uuid.UUID) -> SensitiveFacility:
        facility = self.repo.get_facility_by_id(facility_id)
        if facility is None:
            raise SensitiveFacilityNotFoundError(facility_id)
        if facility.lifecycle_status == "ENTERED_IN_ERROR":
            raise FacilityEnteredInErrorImmutableError(facility_id)
        return facility

    # --- FacilitySector administration (implementation spec §8) -----------------
    def create_facility_sector(
        self,
        *,
        code: str,
        label: str,
        sort_order: int,
        description: str | None,
        actor_user_id: uuid.UUID,
    ) -> FacilitySector:
        if self.repo.get_facility_sector_by_code(code) is not None:
            raise ValidationAppError(f"Facility sector code '{code}' already exists.")
        sector = self.repo.add_facility_sector(
            FacilitySector(
                code=code,
                label=label,
                sort_order=sort_order,
                description=description,
                is_active=True,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self._audit_sector(
            facility_sector_id=sector.id,
            field_name="code",
            old_value=None,
            new_value=code,
            actor_user_id=actor_user_id,
        )
        return sector

    def update_facility_sector(
        self,
        facility_sector_id: int,
        *,
        label: str | None = _UNSET,  # type: ignore[assignment]
        sort_order: int | None = _UNSET,  # type: ignore[assignment]
        description: str | None = _UNSET,  # type: ignore[assignment]
        is_active: bool | None = _UNSET,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> FacilitySector:
        sector = self.repo.get_facility_sector_by_id(facility_sector_id)
        if sector is None:
            raise FacilitySectorNotFoundError(facility_sector_id)

        changed = False
        if label is not _UNSET and label is not None and label != sector.label:
            self._audit_sector(
                facility_sector_id=facility_sector_id,
                field_name="label",
                old_value=sector.label,
                new_value=label,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            sector.label = label
            changed = True
        if sort_order is not _UNSET and sort_order is not None and sort_order != sector.sort_order:
            self._audit_sector(
                facility_sector_id=facility_sector_id,
                field_name="sort_order",
                old_value=sector.sort_order,
                new_value=sort_order,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            sector.sort_order = sort_order
            changed = True
        if description is not _UNSET and description != sector.description:
            self._audit_sector(
                facility_sector_id=facility_sector_id,
                field_name="description",
                old_value=sector.description,
                new_value=description,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            sector.description = description
            changed = True
        if is_active is not _UNSET and is_active is not None and is_active != sector.is_active:
            self._audit_sector(
                facility_sector_id=facility_sector_id,
                field_name="is_active",
                old_value=sector.is_active,
                new_value=is_active,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            sector.is_active = is_active
            changed = True

        if changed:
            sector.updated_by_user_id = actor_user_id
            self.db.flush()
        return sector

    def list_facility_sectors(self) -> list[FacilitySector]:
        return self.repo.list_facility_sectors()

    # --- SensitivityClassification administration --------------------------------
    def create_sensitivity_classification(
        self,
        *,
        code: str,
        label: str,
        sort_order: int,
        description: str | None,
        actor_user_id: uuid.UUID,
    ) -> SensitivityClassification:
        if self.repo.get_sensitivity_classification_by_code(code) is not None:
            raise ValidationAppError(f"Sensitivity classification code '{code}' already exists.")
        classification = self.repo.add_sensitivity_classification(
            SensitivityClassification(
                code=code,
                label=label,
                sort_order=sort_order,
                description=description,
                is_active=True,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self._audit_classification(
            sensitivity_classification_id=classification.id,
            field_name="code",
            old_value=None,
            new_value=code,
            actor_user_id=actor_user_id,
        )
        return classification

    def update_sensitivity_classification(
        self,
        sensitivity_classification_id: int,
        *,
        label: str | None = _UNSET,  # type: ignore[assignment]
        sort_order: int | None = _UNSET,  # type: ignore[assignment]
        description: str | None = _UNSET,  # type: ignore[assignment]
        is_active: bool | None = _UNSET,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> SensitivityClassification:
        classification = self.repo.get_sensitivity_classification_by_id(
            sensitivity_classification_id
        )
        if classification is None:
            raise SensitivityClassificationNotFoundError(sensitivity_classification_id)

        changed = False
        if label is not _UNSET and label is not None and label != classification.label:
            self._audit_classification(
                sensitivity_classification_id=sensitivity_classification_id,
                field_name="label",
                old_value=classification.label,
                new_value=label,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            classification.label = label
            changed = True
        if (
            sort_order is not _UNSET
            and sort_order is not None
            and sort_order != classification.sort_order
        ):
            self._audit_classification(
                sensitivity_classification_id=sensitivity_classification_id,
                field_name="sort_order",
                old_value=classification.sort_order,
                new_value=sort_order,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            classification.sort_order = sort_order
            changed = True
        if description is not _UNSET and description != classification.description:
            self._audit_classification(
                sensitivity_classification_id=sensitivity_classification_id,
                field_name="description",
                old_value=classification.description,
                new_value=description,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            classification.description = description
            changed = True
        if (
            is_active is not _UNSET
            and is_active is not None
            and is_active != classification.is_active
        ):
            self._audit_classification(
                sensitivity_classification_id=sensitivity_classification_id,
                field_name="is_active",
                old_value=classification.is_active,
                new_value=is_active,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            classification.is_active = is_active
            changed = True

        if changed:
            classification.updated_by_user_id = actor_user_id
            self.db.flush()
        return classification

    def list_sensitivity_classifications(self) -> list[SensitivityClassification]:
        return self.repo.list_sensitivity_classifications()

    # --- SensitiveFacility: Create ------------------------------------------------
    def create_facility(
        self,
        *,
        name: str,
        facility_sector_id: int,
        sensitivity_classification_id: int,
        transformer_terminal_ids: list[uuid.UUID] | None,
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> SensitiveFacility:
        if not (
            self.repo.any_facility_sector_exists()
            and self.repo.any_sensitivity_classification_exists()
        ):
            raise ReferenceDataNotSeededError()
        self._require_sector(facility_sector_id)
        self._require_classification(sensitivity_classification_id)

        # Deduped, order-insensitive — a facility's associated terminals
        # are an unordered set (ADR-013), so a duplicate id in the request
        # is silently collapsed, not rejected as invalid.
        terminal_ids = set(transformer_terminal_ids or [])
        for terminal_id in terminal_ids:
            self._require_terminal_exists(terminal_id)

        facility = self.repo.add_facility(
            SensitiveFacility(
                id=uuid.uuid4(),
                name=name,
                facility_sector_id=facility_sector_id,
                sensitivity_classification_id=sensitivity_classification_id,
                lifecycle_status="ACTIVE",
                remarks=remarks,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        for terminal_id in terminal_ids:
            self.repo.add_terminal_association(
                SensitiveFacilityTransformerTerminal(
                    facility_id=facility.id,
                    transformer_terminal_id=terminal_id,
                    added_by_user_id=actor_user_id,
                )
            )
        self._audit_facility(
            facility_id=facility.id,
            field_name="lifecycle_status",
            old_value=None,
            new_value="ACTIVE",
            actor_user_id=actor_user_id,
        )
        return facility

    # --- SensitiveFacility: Update (metadata only — never lifecycle_status) -----
    def update_metadata(
        self,
        facility_id: uuid.UUID,
        *,
        name: str | None = _UNSET,  # type: ignore[assignment]
        facility_sector_id: int | None = _UNSET,  # type: ignore[assignment]
        sensitivity_classification_id: int | None = _UNSET,  # type: ignore[assignment]
        remarks: str | None = _UNSET,  # type: ignore[assignment]
        change_reason: str | None = None,
        actor_user_id: uuid.UUID,
    ) -> SensitiveFacility:
        facility = self._get_editable_facility(facility_id)
        changed = False

        if name is not _UNSET and name is not None and name != facility.name:
            self._audit_facility(
                facility_id=facility_id,
                field_name="name",
                old_value=facility.name,
                new_value=name,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            facility.name = name
            changed = True

        if (
            facility_sector_id is not _UNSET
            and facility_sector_id is not None
            and facility_sector_id != facility.facility_sector_id
        ):
            self._require_sector(facility_sector_id)
            self._audit_facility(
                facility_id=facility_id,
                field_name="facility_sector_id",
                old_value=facility.facility_sector_id,
                new_value=facility_sector_id,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            facility.facility_sector_id = facility_sector_id
            changed = True

        if (
            sensitivity_classification_id is not _UNSET
            and sensitivity_classification_id is not None
            and sensitivity_classification_id != facility.sensitivity_classification_id
        ):
            self._require_classification(sensitivity_classification_id)
            self._audit_facility(
                facility_id=facility_id,
                field_name="sensitivity_classification_id",
                old_value=facility.sensitivity_classification_id,
                new_value=sensitivity_classification_id,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            facility.sensitivity_classification_id = sensitivity_classification_id
            changed = True

        if remarks is not _UNSET and remarks != facility.remarks:
            self._audit_facility(
                facility_id=facility_id,
                field_name="remarks",
                old_value=facility.remarks,
                new_value=remarks,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            facility.remarks = remarks
            changed = True

        if changed:
            facility.updated_by_user_id = actor_user_id
            self.db.flush()
        return facility

    # --- SensitiveFacility: Terminal associations (ADR-013) ---------------------
    def set_terminal_associations(
        self,
        facility_id: uuid.UUID,
        *,
        transformer_terminal_ids: list[uuid.UUID],
        change_reason: str | None,
        actor_user_id: uuid.UUID,
    ) -> SensitiveFacility:
        """Replaces the full set of a facility's currently associated
        Transformer Terminals in one call (ADR-013 decision 3). Diffs the
        requested target set against the current set and writes one audit
        row per actual addition or removal — never one opaque bulk event.
        A no-op call (target set equals current set) makes no change and
        requires no reason."""
        facility = self._get_editable_facility(facility_id)

        target_ids = set(transformer_terminal_ids)
        current_associations = self.repo.list_terminal_associations(facility_id)
        current_ids = {a.transformer_terminal_id for a in current_associations}

        to_add = target_ids - current_ids
        to_remove = current_ids - target_ids

        if not to_add and not to_remove:
            return facility

        # Correction 5 / ADR-013 decision 3 — a mandatory, non-empty reason
        # is required for any actual association change.
        if not change_reason:
            raise ReassignmentReasonRequiredError()

        for terminal_id in to_add:
            self._require_terminal_exists(terminal_id)

        for terminal_id in to_remove:
            self.repo.remove_terminal_association(facility_id, terminal_id)
            self._audit_facility(
                facility_id=facility_id,
                field_name="transformer_terminal_id",
                old_value=terminal_id,
                new_value=None,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )

        for terminal_id in to_add:
            self.repo.add_terminal_association(
                SensitiveFacilityTransformerTerminal(
                    facility_id=facility_id,
                    transformer_terminal_id=terminal_id,
                    added_by_user_id=actor_user_id,
                )
            )
            self._audit_facility(
                facility_id=facility_id,
                field_name="transformer_terminal_id",
                old_value=None,
                new_value=terminal_id,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )

        facility.updated_by_user_id = actor_user_id
        self.db.flush()
        return facility

    # --- Lifecycle (module document §8; implementation spec §7) -----------------
    def _transition(
        self,
        facility_id: uuid.UUID,
        *,
        to_status: str,
        change_reason: str | None,
        actor_user_id: uuid.UUID,
    ) -> SensitiveFacility:
        facility = self.repo.get_facility_by_id(facility_id)
        if facility is None:
            raise SensitiveFacilityNotFoundError(facility_id)
        from_status = facility.lifecycle_status
        if (from_status, to_status) not in _ALLOWED_TRANSITIONS:
            raise InvalidLifecycleTransitionError(from_status=from_status, to_status=to_status)
        if not change_reason:
            raise LifecycleReasonRequiredError()

        self._audit_facility(
            facility_id=facility_id,
            field_name="lifecycle_status",
            old_value=from_status,
            new_value=to_status,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        facility.lifecycle_status = to_status
        facility.updated_by_user_id = actor_user_id
        self.db.flush()
        return facility

    def archive(
        self, facility_id: uuid.UUID, *, change_reason: str | None, actor_user_id: uuid.UUID
    ) -> SensitiveFacility:
        return self._transition(
            facility_id,
            to_status="ARCHIVED",
            change_reason=change_reason,
            actor_user_id=actor_user_id,
        )

    def reactivate(
        self, facility_id: uuid.UUID, *, change_reason: str | None, actor_user_id: uuid.UUID
    ) -> SensitiveFacility:
        return self._transition(
            facility_id,
            to_status="ACTIVE",
            change_reason=change_reason,
            actor_user_id=actor_user_id,
        )

    def mark_entered_in_error(
        self, facility_id: uuid.UUID, *, change_reason: str | None, actor_user_id: uuid.UUID
    ) -> SensitiveFacility:
        return self._transition(
            facility_id,
            to_status="ENTERED_IN_ERROR",
            change_reason=change_reason,
            actor_user_id=actor_user_id,
        )

    # --- Read: facility summary/detail -------------------------------------------
    def _to_summary(
        self,
        facility: SensitiveFacility,
        associations: list[SensitiveFacilityTransformerTerminal] | None = None,
    ) -> SensitiveFacilitySummary:
        if associations is None:
            associations = self.repo.list_terminal_associations(facility.id)
        terminals, aggregate_resolution = self._build_terminal_associations(associations)
        sector = self.repo.get_facility_sector_by_id(facility.facility_sector_id)
        classification = self.repo.get_sensitivity_classification_by_id(
            facility.sensitivity_classification_id
        )
        assert sector is not None  # FK guarantees existence
        assert classification is not None
        return SensitiveFacilitySummary(
            id=facility.id,
            name=facility.name,
            facility_sector=FacilitySectorSummary.model_validate(sector),
            sensitivity_classification=SensitivityClassificationSummary.model_validate(
                classification
            ),
            transformer_terminals=terminals,
            transformer_terminal_resolution=aggregate_resolution,  # type: ignore[arg-type]
            lifecycle_status=facility.lifecycle_status,
            updated_at=facility.updated_at,
        )

    def get_facility_detail(self, facility_id: uuid.UUID) -> SensitiveFacilityDetail | None:
        facility = self.repo.get_facility_by_id(facility_id)
        if facility is None:
            return None
        associations = self.repo.list_terminal_associations(facility_id)
        terminals, aggregate_resolution = self._build_terminal_associations(associations)
        sector = self.repo.get_facility_sector_by_id(facility.facility_sector_id)
        classification = self.repo.get_sensitivity_classification_by_id(
            facility.sensitivity_classification_id
        )
        assert sector is not None
        assert classification is not None
        return SensitiveFacilityDetail(
            id=facility.id,
            name=facility.name,
            facility_sector=FacilitySectorSummary.model_validate(sector),
            sensitivity_classification=SensitivityClassificationSummary.model_validate(
                classification
            ),
            transformer_terminals=terminals,
            transformer_terminal_resolution=aggregate_resolution,  # type: ignore[arg-type]
            lifecycle_status=facility.lifecycle_status,
            remarks=facility.remarks,
            created_at=facility.created_at,
            updated_at=facility.updated_at,
            created_by=self._resolve_user(facility.created_by_user_id),
            updated_by=self._resolve_user(facility.updated_by_user_id),
        )

    def list_facilities(
        self,
        *,
        page: int,
        page_size: int,
        facility_sector_id: int | None = None,
        sensitivity_classification_id: int | None = None,
        lifecycle_status: str | None = None,
        transformer_terminal_id: uuid.UUID | None = None,
        transformer_terminal_resolution: str | None = None,
        substation_id: uuid.UUID | None = None,
    ) -> tuple[list[SensitiveFacilitySummary], int]:
        """Own-column filters apply at the repository level (ADR-013:
        `transformer_terminal_id` matches if *any* associated terminal
        equals the given id — "any associated terminal matches").
        `substation_id` (an attribute this module does not store) and
        `transformer_terminal_resolution` (a computed value) apply here, in
        Python, after resolving each row's terminal associations — mirrors
        ALSF's own established split (`list_functionality`). Correction 4:
        no row is ever dropped because a terminal cannot be resolved —
        only `substation_id` filtering (which requires at least one
        resolved association) naturally excludes facilities with no
        resolvable association, exactly as it should."""
        rows = self.repo.list_facilities(
            facility_sector_id=facility_sector_id,
            sensitivity_classification_id=sensitivity_classification_id,
            lifecycle_status=lifecycle_status,
            transformer_terminal_id=transformer_terminal_id,
        )
        associations_by_facility = self.repo.list_terminal_associations_for_facilities(
            {facility.id for facility in rows}
        )

        enriched: list[SensitiveFacilitySummary] = []
        for facility in rows:
            summary = self._to_summary(facility, associations_by_facility.get(facility.id, []))
            if (
                transformer_terminal_resolution is not None
                and summary.transformer_terminal_resolution != transformer_terminal_resolution
            ):
                continue
            if substation_id is not None and not any(
                t.substation_id == substation_id for t in summary.transformer_terminals
            ):
                continue
            enriched.append(summary)

        total = len(enriched)
        offset = (page - 1) * page_size
        return enriched[offset : offset + page_size], total

    def list_facility_audit_log(
        self, facility_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[SensitiveFacilityAuditLogEntry], int]:
        items, total = self.repo.list_facility_audit_log(
            facility_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            SensitiveFacilityAuditLogEntry(
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

    # --- Stable service contracts (module document §13; implementation spec §9) -
    def has_sensitive_facility(self, transformer_terminal_id: uuid.UUID) -> bool:
        rows = self.repo.list_by_transformer_terminal_ids({transformer_terminal_id})
        return any(r.lifecycle_status == "ACTIVE" for r in rows)

    def get_sensitive_facilities_for_transformer_terminal(
        self, transformer_terminal_id: uuid.UUID
    ) -> list[SensitiveFacilitySummary]:
        rows = self.repo.list_by_transformer_terminal_ids({transformer_terminal_id})
        associations_by_facility = self.repo.list_terminal_associations_for_facilities(
            {r.id for r in rows}
        )
        return [
            self._to_summary(r, associations_by_facility.get(r.id, []))
            for r in rows
            if r.lifecycle_status == "ACTIVE"
        ]

    def get_sensitive_facilities_for_transformer_terminals(
        self, transformer_terminal_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[SensitiveFacilitySummary]]:
        """Batch lookup — completeness-by-construction (implementation
        spec §9): every requested id receives a key in the result, with a
        (possibly empty) list as its value. Resolves entirely against this
        module's own tables; Equipment Registry's own availability does not
        affect completeness.

        ADR-013 — "any associated terminal matches": a facility associated
        with both terminal A and terminal B appears under both A's and B's
        key when both are requested."""
        results: dict[uuid.UUID, list[SensitiveFacilitySummary]] = {
            tid: [] for tid in transformer_terminal_ids
        }
        if not transformer_terminal_ids:
            return results
        rows = self.repo.list_by_transformer_terminal_ids(transformer_terminal_ids)
        associations_by_facility = self.repo.list_terminal_associations_for_facilities(
            {r.id for r in rows}
        )
        for row in rows:
            if row.lifecycle_status != "ACTIVE":
                continue
            row_associations = associations_by_facility.get(row.id, [])
            summary = self._to_summary(row, row_associations)
            matched_ids = {
                a.transformer_terminal_id for a in row_associations
            } & transformer_terminal_ids
            for terminal_id in matched_ids:
                results[terminal_id].append(summary)
        return results

    # --- Dashboard metrics (implementation spec §11 — descriptive only) ---------
    def get_summary_counts(self) -> SensitiveFacilitySummaryCounts:
        by_status = self.repo.count_facilities_by_lifecycle_status()
        all_facilities = self.repo.list_facilities()
        associations_by_facility = self.repo.list_terminal_associations_for_facilities(
            {f.id for f in all_facilities}
        )

        by_sector: dict[str, int] = {}
        by_sensitivity: dict[str, int] = {}
        unresolved = 0
        for facility in all_facilities:
            if facility.lifecycle_status != "ACTIVE":
                continue
            sector = self.repo.get_facility_sector_by_id(facility.facility_sector_id)
            classification = self.repo.get_sensitivity_classification_by_id(
                facility.sensitivity_classification_id
            )
            if sector is not None:
                by_sector[sector.code] = by_sector.get(sector.code, 0) + 1
            if classification is not None:
                by_sensitivity[classification.code] = by_sensitivity.get(classification.code, 0) + 1
            # ADR-013 decision 4 — a facility counts as "unresolved" here if
            # at least one of its associations is unresolved (the same
            # facility-level aggregate reported on summary/detail reads).
            _, aggregate_resolution = self._build_terminal_associations(
                associations_by_facility.get(facility.id, [])
            )
            if aggregate_resolution == "UNRESOLVED":
                unresolved += 1

        return SensitiveFacilitySummaryCounts(
            active_count=by_status.get("ACTIVE", 0),
            archived_count=by_status.get("ARCHIVED", 0),
            entered_in_error_count=by_status.get("ENTERED_IN_ERROR", 0),
            by_sector=by_sector,
            by_sensitivity_classification=by_sensitivity,
            unresolved_terminal_count=unresolved,
        )
