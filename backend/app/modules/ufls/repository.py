"""UFLS repository layer (CLAUDE.md §14) — pure persistence access, no
business rules. This module's own tables only (`ufls_scheme`,
`ufls_scheme_version`, `ufls_stage`, `ufls_direct_assignment`,
`ufls_pocket_assignment`, `ufls_pocket_assignment_opening_point`,
`ufls_audit_log`) — no cross-module repository imports (CLAUDE.md A1).
Composes `scheme_platform.repository`'s own reusable query helpers for
the shared lifecycle queries rather than re-implementing them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.ufls.models import (
    UflsAuditLog,
    UflsDirectAssignment,
    UflsPocketAssignment,
    UflsPocketAssignmentOpeningPoint,
    UflsScheme,
    UflsSchemeVersion,
    UflsStage,
)


class UflsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- UflsScheme -----------------------------------------------------------------
    def add_scheme(self, scheme: UflsScheme) -> UflsScheme:
        self.db.add(scheme)
        self.db.flush()
        return scheme

    def get_scheme(self, ufls_scheme_id: uuid.UUID) -> UflsScheme | None:
        return self.db.get(UflsScheme, ufls_scheme_id)

    def get_scheme_by_name(self, name: str) -> UflsScheme | None:
        stmt = select(UflsScheme).where(UflsScheme.name == name)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_schemes(self) -> list[UflsScheme]:
        stmt = select(UflsScheme).order_by(UflsScheme.name)
        return list(self.db.execute(stmt).scalars().all())

    # --- UflsSchemeVersion ------------------------------------------------------------
    def add_version(self, version: UflsSchemeVersion) -> UflsSchemeVersion:
        self.db.add(version)
        self.db.flush()
        return version

    def get_version(self, version_id: uuid.UUID) -> UflsSchemeVersion | None:
        return self.db.get(UflsSchemeVersion, version_id)

    def delete_version(self, version: UflsSchemeVersion) -> None:
        self.db.delete(version)
        self.db.flush()

    def count_versions_by_stage_setting_set(self, stage_setting_set_id: uuid.UUID) -> int:
        """Every UFLS Scheme Version currently referencing this Stage
        Setting Set, regardless of lifecycle state (Draft or Published) —
        the read-only query backing `UflsService.
        count_versions_referencing_stage_setting_set`, the Stage Setting
        Registry's own reference-check interface for Draft deletion
        (ADR-024)."""
        stmt = (
            select(func.count())
            .select_from(UflsSchemeVersion)
            .where(UflsSchemeVersion.stage_setting_set_id == stage_setting_set_id)
        )
        return self.db.execute(stmt).scalar_one()

    # --- UflsStage --------------------------------------------------------------------
    def add_stage(self, stage: UflsStage) -> UflsStage:
        self.db.add(stage)
        self.db.flush()
        return stage

    def get_stage(self, ufls_stage_id: uuid.UUID) -> UflsStage | None:
        return self.db.get(UflsStage, ufls_stage_id)

    def list_stages(self, scheme_version_id: uuid.UUID) -> list[UflsStage]:
        stmt = select(UflsStage).where(UflsStage.scheme_version_id == scheme_version_id)
        return list(self.db.execute(stmt).scalars().all())

    def delete_stage(self, stage: UflsStage) -> None:
        self.db.delete(stage)
        self.db.flush()

    # --- UflsDirectAssignment -----------------------------------------------------------
    def add_direct_assignment(self, assignment: UflsDirectAssignment) -> UflsDirectAssignment:
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def get_direct_assignment(self, assignment_id: uuid.UUID) -> UflsDirectAssignment | None:
        return self.db.get(UflsDirectAssignment, assignment_id)

    def list_direct_assignments_for_stage(
        self, ufls_stage_id: uuid.UUID
    ) -> list[UflsDirectAssignment]:
        stmt = select(UflsDirectAssignment).where(
            UflsDirectAssignment.ufls_stage_id == ufls_stage_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_direct_assignments_for_version(
        self, scheme_version_id: uuid.UUID
    ) -> list[UflsDirectAssignment]:
        stmt = select(UflsDirectAssignment).where(
            UflsDirectAssignment.scheme_version_id == scheme_version_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_direct_assignment_by_terminal(
        self, scheme_version_id: uuid.UUID, transformer_terminal_id: uuid.UUID
    ) -> UflsDirectAssignment | None:
        stmt = select(UflsDirectAssignment).where(
            UflsDirectAssignment.scheme_version_id == scheme_version_id,
            UflsDirectAssignment.transformer_terminal_id == transformer_terminal_id,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def delete_direct_assignment(self, assignment: UflsDirectAssignment) -> None:
        self.db.delete(assignment)
        self.db.flush()

    # --- UflsPocketAssignment -----------------------------------------------------------
    def add_pocket_assignment(self, assignment: UflsPocketAssignment) -> UflsPocketAssignment:
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def get_pocket_assignment(self, assignment_id: uuid.UUID) -> UflsPocketAssignment | None:
        return self.db.get(UflsPocketAssignment, assignment_id)

    def list_pocket_assignments_for_stage(
        self, ufls_stage_id: uuid.UUID
    ) -> list[UflsPocketAssignment]:
        stmt = select(UflsPocketAssignment).where(
            UflsPocketAssignment.ufls_stage_id == ufls_stage_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_pocket_assignments_for_version(
        self, scheme_version_id: uuid.UUID
    ) -> list[UflsPocketAssignment]:
        stmt = select(UflsPocketAssignment).where(
            UflsPocketAssignment.scheme_version_id == scheme_version_id
        )
        return list(self.db.execute(stmt).scalars().all())

    def delete_pocket_assignment(self, assignment: UflsPocketAssignment) -> None:
        self.db.delete(assignment)
        self.db.flush()

    def add_opening_point(
        self, opening_point: UflsPocketAssignmentOpeningPoint
    ) -> UflsPocketAssignmentOpeningPoint:
        self.db.add(opening_point)
        self.db.flush()
        return opening_point

    def list_opening_points(
        self, ufls_pocket_assignment_id: uuid.UUID
    ) -> list[UflsPocketAssignmentOpeningPoint]:
        stmt = select(UflsPocketAssignmentOpeningPoint).where(
            UflsPocketAssignmentOpeningPoint.ufls_pocket_assignment_id == ufls_pocket_assignment_id
        )
        return list(self.db.execute(stmt).scalars().all())

    # --- Audit log ----------------------------------------------------------------------
    def add_audit_entry(self, entry: UflsAuditLog) -> UflsAuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def list_audit_log(
        self, entity_type: str, entity_id: str, *, offset: int, limit: int
    ) -> list[UflsAuditLog]:
        stmt = (
            select(UflsAuditLog)
            .where(UflsAuditLog.entity_type == entity_type, UflsAuditLog.entity_id == entity_id)
            .order_by(UflsAuditLog.changed_at.desc(), UflsAuditLog.log_id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.db.execute(stmt).scalars().all())
