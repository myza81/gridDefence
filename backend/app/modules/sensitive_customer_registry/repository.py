"""Sensitive Customer Registry repository layer (CLAUDE.md §14) — pure
persistence access. No business rules, no permission checks, no audit
writing live here — that is `service.py`'s responsibility.

This repository touches exactly this module's own five tables
(`sensitive_facility`, `sensitive_facility_transformer_terminal`,
`facility_sector`, `sensitivity_classification`,
`sensitive_customer_registry_audit_log`) — no cross-module repository
imports, per CLAUDE.md A1. Filtering by substation/voltage-level
(attributes this module does not itself store) and Transformer Terminal
resolution status are resolved by the service layer composing this
repository's own-column filters with read-only calls to
`EquipmentRegistryService` — never by a cross-module SQL join here.

`sensitive_facility_transformer_terminal` (ADR-013) is a many-to-many
association, not a facility column — its own query/add/remove methods sit
below the `SensitiveFacility` methods.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.sensitive_customer_registry.models import (
    FacilitySector,
    SensitiveCustomerRegistryAuditLog,
    SensitiveFacility,
    SensitiveFacilityTransformerTerminal,
    SensitivityClassification,
)


class SensitiveCustomerRegistryRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- SensitiveFacility --------------------------------------------------
    def add_facility(self, facility: SensitiveFacility) -> SensitiveFacility:
        self.db.add(facility)
        self.db.flush()
        return facility

    def get_facility_by_id(self, facility_id: uuid.UUID) -> SensitiveFacility | None:
        return self.db.get(SensitiveFacility, facility_id)

    def list_facilities(
        self,
        *,
        facility_sector_id: int | None = None,
        sensitivity_classification_id: int | None = None,
        lifecycle_status: str | None = None,
        transformer_terminal_id: uuid.UUID | None = None,
    ) -> list[SensitiveFacility]:
        """Filters only on this module's own columns. Unpaginated by
        design — pagination happens at the service layer, after
        cross-module identity/resolution enrichment (mirrors ALSF's own
        `list_all` precedent, acceptable for a manually-maintained,
        modestly-sized static registry, CLAUDE.md §21).

        `transformer_terminal_id` (ADR-013 — "any associated terminal
        matches") is an EXISTS filter against the association table, not a
        column comparison — a facility matches if it has *any* current
        association with the given terminal."""
        stmt = select(SensitiveFacility)
        if facility_sector_id is not None:
            stmt = stmt.where(SensitiveFacility.facility_sector_id == facility_sector_id)
        if sensitivity_classification_id is not None:
            stmt = stmt.where(
                SensitiveFacility.sensitivity_classification_id == sensitivity_classification_id
            )
        if lifecycle_status is not None:
            stmt = stmt.where(SensitiveFacility.lifecycle_status == lifecycle_status)
        if transformer_terminal_id is not None:
            stmt = stmt.where(
                SensitiveFacility.id.in_(
                    select(SensitiveFacilityTransformerTerminal.facility_id).where(
                        SensitiveFacilityTransformerTerminal.transformer_terminal_id
                        == transformer_terminal_id
                    )
                )
            )
        stmt = stmt.order_by(SensitiveFacility.updated_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def list_by_transformer_terminal_ids(
        self, transformer_terminal_ids: set[uuid.UUID]
    ) -> list[SensitiveFacility]:
        """Batch lookup — resolves entirely against this module's own
        tables (implementation spec §9). Includes every lifecycle status;
        the service layer filters to Active for the public contract.

        ADR-013 — "any associated terminal matches": a facility with
        several associated terminals, only one of which is in
        `transformer_terminal_ids`, is still returned exactly once
        (`distinct()` on the join)."""
        if not transformer_terminal_ids:
            return []
        stmt = (
            select(SensitiveFacility)
            .join(
                SensitiveFacilityTransformerTerminal,
                SensitiveFacilityTransformerTerminal.facility_id == SensitiveFacility.id,
            )
            .where(
                SensitiveFacilityTransformerTerminal.transformer_terminal_id.in_(
                    transformer_terminal_ids
                )
            )
            .distinct()
        )
        return list(self.db.execute(stmt).scalars().all())

    def count_facilities_by_lifecycle_status(self) -> dict[str, int]:
        stmt = select(SensitiveFacility.lifecycle_status, func.count()).group_by(
            SensitiveFacility.lifecycle_status
        )
        return {status: count for status, count in self.db.execute(stmt).all()}

    # --- SensitiveFacilityTransformerTerminal (ADR-013 association) -------------
    def list_terminal_associations(
        self, facility_id: uuid.UUID
    ) -> list[SensitiveFacilityTransformerTerminal]:
        stmt = (
            select(SensitiveFacilityTransformerTerminal)
            .where(SensitiveFacilityTransformerTerminal.facility_id == facility_id)
            .order_by(SensitiveFacilityTransformerTerminal.added_at)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_terminal_associations_for_facilities(
        self, facility_ids: set[uuid.UUID]
    ) -> dict[uuid.UUID, list[SensitiveFacilityTransformerTerminal]]:
        """Batch-fetches associations for several facilities in one query —
        used by list views to avoid one query per row (N+1), mirroring
        Equipment Registry's own `list_transformer_terminals_for_transformers`."""
        if not facility_ids:
            return {}
        stmt = (
            select(SensitiveFacilityTransformerTerminal)
            .where(SensitiveFacilityTransformerTerminal.facility_id.in_(facility_ids))
            .order_by(SensitiveFacilityTransformerTerminal.added_at)
        )
        by_facility: dict[uuid.UUID, list[SensitiveFacilityTransformerTerminal]] = {}
        for association in self.db.execute(stmt).scalars().all():
            by_facility.setdefault(association.facility_id, []).append(association)
        return by_facility

    def add_terminal_association(
        self, association: SensitiveFacilityTransformerTerminal
    ) -> SensitiveFacilityTransformerTerminal:
        self.db.add(association)
        self.db.flush()
        return association

    def remove_terminal_association(
        self, facility_id: uuid.UUID, transformer_terminal_id: uuid.UUID
    ) -> None:
        association = self.db.get(
            SensitiveFacilityTransformerTerminal, (facility_id, transformer_terminal_id)
        )
        if association is not None:
            self.db.delete(association)
            self.db.flush()

    # --- FacilitySector -------------------------------------------------------
    def add_facility_sector(self, sector: FacilitySector) -> FacilitySector:
        self.db.add(sector)
        self.db.flush()
        return sector

    def get_facility_sector_by_id(self, facility_sector_id: int) -> FacilitySector | None:
        return self.db.get(FacilitySector, facility_sector_id)

    def get_facility_sector_by_code(self, code: str) -> FacilitySector | None:
        stmt = select(FacilitySector).where(FacilitySector.code == code)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_facility_sectors(self) -> list[FacilitySector]:
        stmt = select(FacilitySector).order_by(FacilitySector.sort_order, FacilitySector.label)
        return list(self.db.execute(stmt).scalars().all())

    def any_facility_sector_exists(self) -> bool:
        return self.db.execute(select(FacilitySector.id).limit(1)).first() is not None

    # --- SensitivityClassification ---------------------------------------------
    def add_sensitivity_classification(
        self, classification: SensitivityClassification
    ) -> SensitivityClassification:
        self.db.add(classification)
        self.db.flush()
        return classification

    def get_sensitivity_classification_by_id(
        self, sensitivity_classification_id: int
    ) -> SensitivityClassification | None:
        return self.db.get(SensitivityClassification, sensitivity_classification_id)

    def get_sensitivity_classification_by_code(self, code: str) -> SensitivityClassification | None:
        stmt = select(SensitivityClassification).where(SensitivityClassification.code == code)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_sensitivity_classifications(self) -> list[SensitivityClassification]:
        stmt = select(SensitivityClassification).order_by(
            SensitivityClassification.sort_order, SensitivityClassification.label
        )
        return list(self.db.execute(stmt).scalars().all())

    def any_sensitivity_classification_exists(self) -> bool:
        return self.db.execute(select(SensitivityClassification.id).limit(1)).first() is not None

    # --- Audit log (shared, polymorphic) ----------------------------------------
    def add_audit_log(
        self, entry: SensitiveCustomerRegistryAuditLog
    ) -> SensitiveCustomerRegistryAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_facility_audit_log(
        self, facility_id: uuid.UUID, *, offset: int, limit: int
    ) -> tuple[list[SensitiveCustomerRegistryAuditLog], int]:
        total = self.db.execute(
            select(func.count())
            .select_from(SensitiveCustomerRegistryAuditLog)
            .where(SensitiveCustomerRegistryAuditLog.sensitive_facility_id == facility_id)
        ).scalar_one()

        stmt = (
            select(SensitiveCustomerRegistryAuditLog)
            .where(SensitiveCustomerRegistryAuditLog.sensitive_facility_id == facility_id)
            # `log_id.desc()` is a deterministic tiebreaker: every field
            # changed by a single create()/update_metadata()/lifecycle call
            # is audited within the same transaction, so those rows share
            # the exact same `changed_at` value (PostgreSQL's `now()` is
            # transaction-consistent) — sorting on `changed_at` alone
            # leaves their relative order undefined by SQL. `log_id`, an
            # autoincrementing PK, is always monotonically increasing in
            # insertion order, so it resolves the tie deterministically
            # (review finding — audit ordering must be deterministic).
            .order_by(
                SensitiveCustomerRegistryAuditLog.changed_at.desc(),
                SensitiveCustomerRegistryAuditLog.log_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        )
        items = list(self.db.execute(stmt).scalars().all())
        return items, total
