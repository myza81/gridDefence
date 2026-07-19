"""UFLS service layer (CLAUDE.md §14) — business rules, transactions,
orchestration. Composes the Shared Defence-Scheme Platform
(`scheme_platform`) for lifecycle transitions rather than re-implementing
them; composes Findings and Publication Governance
(`findings_publication_governance`) for Publication Treatment resolution
and `PublicationRecord` creation rather than duplicating that mechanism;
consumes Substation Registry, Equipment Registry, the Automatic Load
Shedding Functionality Registry, and the Sensitive Customer Registry
exclusively through their own service layers (CLAUDE.md A1) — never
their repositories directly.

No engineering calculation of any kind lives here: `target_mw` is always
an external-study, engineer-entered value (never computed); this service
never determines a required shedding quantum, never designs a stage
structure, and never resolves a Boundary Pocket's engineering adequacy —
it only records, validates structural completeness, and orchestrates.

Flush-only, never commits (mirrors every other module's own established
transaction-boundary discipline) — the router's own request/response
cycle (or a future caller) commits once, itself.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.modules.automatic_load_shedding_functionality.service import (
    AutomaticLoadSheddingFunctionalityService,
)
from app.modules.continuous_evaluation.schemas import ChangeDescriptor
from app.modules.continuous_evaluation.service import ContinuousEvaluationService
from app.modules.equipment_registry.service import EquipmentRegistryService
from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)
from app.modules.findings_publication_governance.publication import (
    AcknowledgementInput,
    PublicationPrerequisiteResult,
    PublicationRequest,
)
from app.modules.findings_publication_governance.service import PublicationRecordService
from app.modules.iam.service import IAMService
from app.modules.network_model.schemas import BoundaryPocketEvaluationRequest
from app.modules.network_model.service import NetworkModelService
from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus
from app.modules.scheme_platform.repository import get_current_published, list_versions
from app.modules.scheme_platform.service import SchemeVersionLifecycleService
from app.modules.sensitive_customer_registry.service import SensitiveCustomerRegistryService
from app.modules.stage_setting_registry.service import StageSettingRegistryService
from app.modules.substation_registry.service import SubstationService
from app.modules.ufls.exceptions import (
    DirectAndPocketOverlapError,
    IneffectiveBoundaryError,
    InvalidTerminalReferenceError,
    NoStageSettingSetSelectedError,
    StageSettingNotInSelectedSetError,
    StageSettingSetNotFoundError,
    StageSettingSetNotPublishedError,
    StageSettingSetSchemeTypeMismatchError,
    SubstationNotEligibleForAssignmentError,
    TerminalAlreadyAssignedError,
    UflsDirectAssignmentNotFoundError,
    UflsPocketAssignmentNotFoundError,
    UflsSchemeNotFoundError,
    UflsSchemeVersionNotFoundError,
    UflsStageNotFoundError,
    VersionNotEditableError,
)
from app.modules.ufls.models import (
    UflsAuditLog,
    UflsDirectAssignment,
    UflsPocketAssignment,
    UflsPocketAssignmentOpeningPoint,
    UflsScheme,
    UflsSchemeVersion,
    UflsStage,
)
from app.modules.ufls.repository import UflsRepository
from app.modules.ufls.schemas import (
    PublicationPrerequisiteSummary,
    PublicationReviewResult,
    PublishResult,
    UflsDirectAssignmentDetail,
    UflsPocketAssignmentDetail,
    UflsSchemeDetail,
    UflsSchemeSummary,
    UflsSchemeVersionDetail,
    UflsSchemeVersionSummary,
    UflsStageDetail,
    UflsStageMwSummary,
    UflsStageTriggerSummary,
    UflsVersionEngineeringSummary,
)
from app.reference_data.repository import ReferenceDataRepository

_EXCLUDED_GRID_OWNER_CODES = frozenset({"IPP", "LSS"})  # ufls-module.md §9 rule 8
_INELIGIBLE_OPERATIONAL_STATUS_CODES = frozenset(
    {"DECOMMISSIONED", "RETIRED", "ENTERED_IN_ERROR"}
)  # ufls-module.md §9 rule 12


class UflsService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = UflsRepository(db)
        self.lifecycle = SchemeVersionLifecycleService(db, source_module="ufls")
        self.publication_record = PublicationRecordService(db)
        self.substation_registry = SubstationService(db)
        self.equipment_registry = EquipmentRegistryService(db)
        self.alsf = AutomaticLoadSheddingFunctionalityService(db)
        self.sensitive_customer = SensitiveCustomerRegistryService(db)
        self.stage_setting_registry = StageSettingRegistryService(db)
        self.network_model = NetworkModelService(db)
        self.reference_data = ReferenceDataRepository(db)
        self.continuous_evaluation = ContinuousEvaluationService(db)
        self.iam = IAMService(db)

    # --- UflsScheme ------------------------------------------------------------------
    def create_scheme(
        self, *, name: str, description: str | None, actor_user_id: uuid.UUID
    ) -> UflsScheme:
        scheme = self.repo.add_scheme(
            UflsScheme(name=name, description=description, created_by_user_id=actor_user_id)
        )
        self._audit("UflsScheme", str(scheme.ufls_scheme_id), "created", None, name, actor_user_id)
        self._notify_change(entity_type="scheme", entity_id=scheme.ufls_scheme_id, action="created")
        return scheme

    def get_scheme(self, ufls_scheme_id: uuid.UUID) -> UflsScheme:
        scheme = self.repo.get_scheme(ufls_scheme_id)
        if scheme is None:
            raise UflsSchemeNotFoundError(ufls_scheme_id)
        return scheme

    def list_schemes(self) -> list[UflsScheme]:
        return self.repo.list_schemes()

    def get_current_published_version(self, ufls_scheme_id: uuid.UUID) -> UflsSchemeVersion | None:
        return get_current_published(self.db, UflsSchemeVersion, ufls_scheme_id)

    def list_scheme_versions(self, ufls_scheme_id: uuid.UUID) -> list[UflsSchemeVersion]:
        return list_versions(self.db, UflsSchemeVersion, ufls_scheme_id)

    def count_versions_referencing_stage_setting_set(self, stage_setting_set_id: uuid.UUID) -> int:
        """UFLS's own side of the Stage Setting Registry's read-only
        reference-check interface (ADR-024) — implements
        `stage_setting_registry.reference_check.SchemeVersionReferenceChecker`.
        Queries UFLS's own table only (CLAUDE.md A1); the Stage Setting
        Registry never reads `ufls_scheme_version` directly."""
        return self.repo.count_versions_by_stage_setting_set(stage_setting_set_id)

    # --- UflsSchemeVersion lifecycle ---------------------------------------------------
    def create_draft_version(
        self,
        ufls_scheme_id: uuid.UUID,
        *,
        copied_from_version_id: uuid.UUID | None,
        actor_user_id: uuid.UUID,
    ) -> UflsSchemeVersion:
        """Creates a new Draft. If `copied_from_version_id` is supplied,
        copies its own structure (stages, direct/pocket assignments) —
        never Publication status, acknowledgements, historical findings,
        or target MW (shared-defence-scheme-domain-model.md §5). Always
        starts as `Draft`, regardless of the source version's own
        lifecycle state."""
        self.get_scheme(ufls_scheme_id)  # existence check
        version = UflsSchemeVersion(scheme_id=ufls_scheme_id)
        # Not `self.repo.add_version` — that flushes immediately, before
        # `create_draft` below populates the NOT NULL `version_number`/
        # `lifecycle_status` fields (mirrors scheme_platform.service's own
        # documented contract: the caller only adds the instance to the
        # session; `create_draft` performs the one flush once those shared
        # fields are stamped).
        self.db.add(version)
        self.lifecycle.create_draft(
            version, model_class=UflsSchemeVersion, scheme_id=ufls_scheme_id
        )

        if copied_from_version_id is not None:
            source = self.get_version(copied_from_version_id)
            version.stage_setting_set_id = source.stage_setting_set_id
            self.db.flush()
            for source_stage in self.repo.list_stages(source.version_id):
                new_stage = self.repo.add_stage(
                    UflsStage(
                        scheme_version_id=version.version_id,
                        stage_setting_id=source_stage.stage_setting_id,
                    )
                )
                for direct in self.repo.list_direct_assignments_for_stage(
                    source_stage.ufls_stage_id
                ):
                    self.repo.add_direct_assignment(
                        UflsDirectAssignment(
                            ufls_stage_id=new_stage.ufls_stage_id,
                            scheme_version_id=version.version_id,
                            transformer_terminal_id=direct.transformer_terminal_id,
                        )
                    )
                for pocket in self.repo.list_pocket_assignments_for_stage(
                    source_stage.ufls_stage_id
                ):
                    new_pocket = self.repo.add_pocket_assignment(
                        UflsPocketAssignment(
                            ufls_stage_id=new_stage.ufls_stage_id,
                            scheme_version_id=version.version_id,
                        )
                    )
                    for opening_point in self.repo.list_opening_points(
                        pocket.ufls_pocket_assignment_id
                    ):
                        self.repo.add_opening_point(
                            UflsPocketAssignmentOpeningPoint(
                                ufls_pocket_assignment_id=new_pocket.ufls_pocket_assignment_id,
                                circuit_terminal_id=opening_point.circuit_terminal_id,
                            )
                        )

        self._audit(
            "UflsSchemeVersion", str(version.version_id), "created", None, "Draft", actor_user_id
        )
        return version

    def get_version(self, version_id: uuid.UUID) -> UflsSchemeVersion:
        version = self.repo.get_version(version_id)
        if version is None:
            raise UflsSchemeVersionNotFoundError(version_id)
        return version

    def delete_draft_version(self, version_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        version = self.get_version(version_id)
        self.lifecycle.delete_draft(version)
        self.repo.delete_version(version)
        self._audit("UflsSchemeVersion", str(version_id), "deleted", "Draft", None, actor_user_id)

    def update_version_metadata(
        self,
        version_id: uuid.UUID,
        *,
        stage_setting_set_id: uuid.UUID | None,
        study_reference: str | None,
        effective_date,
        topology_version_id: uuid.UUID | None,
        load_snapshot_id: uuid.UUID | None,
        engineering_remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> UflsSchemeVersion:
        version = self.get_version(version_id)
        self._require_editable(version)

        set_changed = (
            stage_setting_set_id is not None
            and stage_setting_set_id != version.stage_setting_set_id
        )
        if set_changed:
            self._validate_stage_setting_set(stage_setting_set_id)
            version.stage_setting_set_id = stage_setting_set_id
        if study_reference is not None:
            version.study_reference = study_reference
        if effective_date is not None:
            version.effective_date = effective_date
        if topology_version_id is not None:
            version.topology_version_id = topology_version_id
        if load_snapshot_id is not None:
            version.load_snapshot_id = load_snapshot_id
        if engineering_remarks is not None:
            version.engineering_remarks = engineering_remarks
        self.db.flush()
        self._audit(
            "UflsSchemeVersion", str(version_id), "metadata_updated", None, None, actor_user_id
        )
        self._notify_change(
            entity_type="scheme_version", entity_id=version_id, action="draft_updated"
        )
        return version

    def _validate_stage_setting_set(self, stage_setting_set_id: uuid.UUID) -> None:
        """ADR-024 (Selection-Time Validation Correction): a Draft
        version may select only a `PUBLISHED` Stage Setting Set of the
        matching scheme type — `DRAFT`/`ENTERED_IN_ERROR` and a scheme-
        type mismatch are both rejected here, at selection time, never
        deferred to the `UFLS_STAGE_SETTING_SET_PUBLISHED` Publish-time
        prerequisite alone (stage-setting-set-architecture.md §6)."""
        stage_setting_set = self.stage_setting_registry.get_set(stage_setting_set_id)
        if stage_setting_set is None:
            raise StageSettingSetNotFoundError(stage_setting_set_id)
        if stage_setting_set.scheme_type != "UFLS":
            raise StageSettingSetSchemeTypeMismatchError(
                stage_setting_set_id, stage_setting_set.scheme_type
            )
        if stage_setting_set.status != "PUBLISHED":
            raise StageSettingSetNotPublishedError(stage_setting_set_id, stage_setting_set.status)

    def enter_in_error(
        self, version_id: uuid.UUID, *, reason: str, actor_user_id: uuid.UUID
    ) -> UflsSchemeVersion:
        version = self.get_version(version_id)
        self.lifecycle.enter_in_error(version, reason=reason, actor_user_id=actor_user_id)
        self._audit(
            "UflsSchemeVersion",
            str(version_id),
            "entered_in_error",
            None,
            None,
            actor_user_id,
            change_reason=reason,
        )
        return version

    def _require_editable(self, version: UflsSchemeVersion) -> None:
        if version.lifecycle_status != SchemeVersionLifecycleStatus.DRAFT.value:
            raise VersionNotEditableError(version.version_id, version.lifecycle_status)

    # --- UflsStage --------------------------------------------------------------------
    def add_stage(
        self,
        version_id: uuid.UUID,
        *,
        stage_setting_id: uuid.UUID,
        target_mw: Decimal | None,
        engineering_remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> UflsStage:
        version = self.get_version(version_id)
        self._require_editable(version)
        if version.stage_setting_set_id is None:
            raise NoStageSettingSetSelectedError()

        setting = self.stage_setting_registry.get_setting(stage_setting_id)
        if setting is None or setting.stage_setting_set_id != version.stage_setting_set_id:
            raise StageSettingNotInSelectedSetError(stage_setting_id, version.stage_setting_set_id)

        stage = self.repo.add_stage(
            UflsStage(
                scheme_version_id=version_id,
                stage_setting_id=stage_setting_id,
                target_mw=target_mw,
                engineering_remarks=engineering_remarks,
            )
        )
        self._audit("UflsStage", str(stage.ufls_stage_id), "created", None, None, actor_user_id)
        self._notify_change(entity_type="stage", entity_id=stage.ufls_stage_id, action="created")
        return stage

    def update_stage(
        self,
        ufls_stage_id: uuid.UUID,
        *,
        target_mw: Decimal | None,
        engineering_remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> UflsStage:
        stage = self.get_stage(ufls_stage_id)
        version = self.get_version(stage.scheme_version_id)
        self._require_editable(version)
        if target_mw is not None:
            stage.target_mw = target_mw
        if engineering_remarks is not None:
            stage.engineering_remarks = engineering_remarks
        self.db.flush()
        self._audit("UflsStage", str(ufls_stage_id), "updated", None, None, actor_user_id)
        self._notify_change(entity_type="stage", entity_id=ufls_stage_id, action="updated")
        return stage

    def get_stage(self, ufls_stage_id: uuid.UUID) -> UflsStage:
        stage = self.repo.get_stage(ufls_stage_id)
        if stage is None:
            raise UflsStageNotFoundError(ufls_stage_id)
        return stage

    def list_stages(self, version_id: uuid.UUID) -> list[UflsStage]:
        return self.repo.list_stages(version_id)

    def remove_stage(self, ufls_stage_id: uuid.UUID, *, actor_user_id: uuid.UUID) -> None:
        stage = self.get_stage(ufls_stage_id)
        version = self.get_version(stage.scheme_version_id)
        self._require_editable(version)
        self.repo.delete_stage(stage)
        self._audit("UflsStage", str(ufls_stage_id), "removed", None, None, actor_user_id)
        self._notify_change(entity_type="stage", entity_id=ufls_stage_id, action="removed")

    # --- Direct Assignments -------------------------------------------------------------
    def add_direct_assignment(
        self,
        ufls_stage_id: uuid.UUID,
        *,
        transformer_terminal_id: uuid.UUID,
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> UflsDirectAssignment:
        stage = self.get_stage(ufls_stage_id)
        version = self.get_version(stage.scheme_version_id)
        self._require_editable(version)

        substation_id = self._validate_terminal_eligible(transformer_terminal_id)
        if self.repo.get_direct_assignment_by_terminal(version.version_id, transformer_terminal_id):
            raise TerminalAlreadyAssignedError(transformer_terminal_id)
        self._validate_no_pocket_overlap(version.version_id, {substation_id})

        assignment = self.repo.add_direct_assignment(
            UflsDirectAssignment(
                ufls_stage_id=ufls_stage_id,
                scheme_version_id=version.version_id,
                transformer_terminal_id=transformer_terminal_id,
                remarks=remarks,
            )
        )
        self._audit(
            "UflsDirectAssignment",
            str(assignment.ufls_direct_assignment_id),
            "created",
            None,
            None,
            actor_user_id,
        )
        self._notify_change(
            entity_type="direct_assignment",
            entity_id=assignment.ufls_direct_assignment_id,
            action="created",
        )
        return assignment

    def move_direct_assignment(
        self,
        assignment_id: uuid.UUID,
        *,
        target_ufls_stage_id: uuid.UUID,
        actor_user_id: uuid.UUID,
    ) -> UflsDirectAssignment:
        assignment = self.get_direct_assignment(assignment_id)
        version = self.get_version(assignment.scheme_version_id)
        self._require_editable(version)
        target_stage = self.get_stage(target_ufls_stage_id)
        if target_stage.scheme_version_id != version.version_id:
            raise UflsStageNotFoundError(target_ufls_stage_id)
        assignment.ufls_stage_id = target_ufls_stage_id
        self.db.flush()
        self._audit("UflsDirectAssignment", str(assignment_id), "moved", None, None, actor_user_id)
        self._notify_change(
            entity_type="direct_assignment", entity_id=assignment_id, action="moved"
        )
        return assignment

    def get_direct_assignment(self, assignment_id: uuid.UUID) -> UflsDirectAssignment:
        assignment = self.repo.get_direct_assignment(assignment_id)
        if assignment is None:
            raise UflsDirectAssignmentNotFoundError(assignment_id)
        return assignment

    def list_direct_assignments(self, ufls_stage_id: uuid.UUID) -> list[UflsDirectAssignment]:
        return self.repo.list_direct_assignments_for_stage(ufls_stage_id)

    def remove_direct_assignment(
        self, assignment_id: uuid.UUID, *, actor_user_id: uuid.UUID
    ) -> None:
        assignment = self.get_direct_assignment(assignment_id)
        version = self.get_version(assignment.scheme_version_id)
        self._require_editable(version)
        self.repo.delete_direct_assignment(assignment)
        self._audit(
            "UflsDirectAssignment", str(assignment_id), "removed", None, None, actor_user_id
        )
        self._notify_change(
            entity_type="direct_assignment", entity_id=assignment_id, action="removed"
        )

    def _validate_terminal_eligible(self, transformer_terminal_id: uuid.UUID) -> uuid.UUID:
        """Rules 8/12 (corrected numbering) — excluded grid-owner
        classification, ineligible operational status. Returns the
        resolved `substation_id` for the caller's own further use."""
        identity = self.equipment_registry.get_transformer_terminal_identity(
            transformer_terminal_id
        )
        if identity is None:
            raise InvalidTerminalReferenceError(transformer_terminal_id)

        substation = self.substation_registry.get_substation(identity.substation_id)
        grid_owner = self.reference_data.get_grid_owner(substation.grid_owner_id)
        if grid_owner is not None and grid_owner.code in _EXCLUDED_GRID_OWNER_CODES:
            raise SubstationNotEligibleForAssignmentError(
                identity.substation_id,
                f"excluded grid-owner classification '{grid_owner.code}'",
            )
        operational_status = self.reference_data.get_operational_status(
            substation.operational_status_id
        )
        if (
            operational_status is not None
            and operational_status.code in _INELIGIBLE_OPERATIONAL_STATUS_CODES
        ):
            raise SubstationNotEligibleForAssignmentError(
                identity.substation_id,
                f"operational status '{operational_status.code}'",
            )
        return identity.substation_id

    # --- Pocket Assignments -------------------------------------------------------------
    def add_pocket_assignment(
        self,
        ufls_stage_id: uuid.UUID,
        *,
        circuit_terminal_ids: list[uuid.UUID],
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> UflsPocketAssignment:
        stage = self.get_stage(ufls_stage_id)
        version = self.get_version(stage.scheme_version_id)
        self._require_editable(version)

        evaluation = self.network_model.evaluate_boundary(
            BoundaryPocketEvaluationRequest(
                circuit_terminal_ids=circuit_terminal_ids,
                topology_version_id=version.topology_version_id,
            )
        )
        if not evaluation.is_boundary_effective:
            raise IneffectiveBoundaryError()

        island_substation_ids = {
            s.substation_id for island in evaluation.isolated_islands for s in island.substations
        }
        self._validate_no_pocket_overlap(version.version_id, island_substation_ids)

        pocket = self.repo.add_pocket_assignment(
            UflsPocketAssignment(
                ufls_stage_id=ufls_stage_id, scheme_version_id=version.version_id, remarks=remarks
            )
        )
        for circuit_terminal_id in circuit_terminal_ids:
            self.repo.add_opening_point(
                UflsPocketAssignmentOpeningPoint(
                    ufls_pocket_assignment_id=pocket.ufls_pocket_assignment_id,
                    circuit_terminal_id=circuit_terminal_id,
                )
            )
        self._audit(
            "UflsPocketAssignment",
            str(pocket.ufls_pocket_assignment_id),
            "created",
            None,
            None,
            actor_user_id,
        )
        self._notify_change(
            entity_type="pocket_assignment",
            entity_id=pocket.ufls_pocket_assignment_id,
            action="created",
        )
        return pocket

    def get_pocket_assignment(self, assignment_id: uuid.UUID) -> UflsPocketAssignment:
        assignment = self.repo.get_pocket_assignment(assignment_id)
        if assignment is None:
            raise UflsPocketAssignmentNotFoundError(assignment_id)
        return assignment

    def list_pocket_assignments(self, ufls_stage_id: uuid.UUID) -> list[UflsPocketAssignment]:
        return self.repo.list_pocket_assignments_for_stage(ufls_stage_id)

    def remove_pocket_assignment(
        self, assignment_id: uuid.UUID, *, actor_user_id: uuid.UUID
    ) -> None:
        assignment = self.get_pocket_assignment(assignment_id)
        version = self.get_version(assignment.scheme_version_id)
        self._require_editable(version)
        self.repo.delete_pocket_assignment(assignment)
        self._audit(
            "UflsPocketAssignment", str(assignment_id), "removed", None, None, actor_user_id
        )
        self._notify_change(
            entity_type="pocket_assignment", entity_id=assignment_id, action="removed"
        )

    def _validate_no_pocket_overlap(
        self, version_id: uuid.UUID, candidate_substation_ids: set[uuid.UUID]
    ) -> None:
        """ufls-module.md §9 rule 7: a substation may not simultaneously
        be a direct assignment and appear within any pocket assignment's
        derived substation set, within the same version."""
        if not candidate_substation_ids:
            return
        direct_substation_ids = {
            self.equipment_registry.get_transformer_terminal_identity(
                a.transformer_terminal_id
            ).substation_id
            for a in self.repo.list_direct_assignments_for_version(version_id)
        }
        overlap = candidate_substation_ids & direct_substation_ids
        if overlap:
            raise DirectAndPocketOverlapError(next(iter(overlap)))

    # --- Findings (task §7) -------------------------------------------------------------
    def compute_findings(self, version_id: uuid.UUID) -> list[Finding]:
        """ALSF capability and Sensitive Customer findings — never
        silently remove a candidate or make the engineering decision
        (scheme-engineering-principles.md §6). MW tolerance findings are
        deliberately not computed here — they belong to Continuous
        Evaluation's own MW tolerance detector (Sprint 5), invoked
        separately via `UflsEvaluationRequestProvider` (evaluation.py)."""
        findings: list[Finding] = []

        direct_assignments = self.repo.list_direct_assignments_for_version(version_id)
        terminal_ids = {a.transformer_terminal_id for a in direct_assignments}
        sensitive_by_terminal = (
            self.sensitive_customer.get_sensitive_facilities_for_transformer_terminals(terminal_ids)
        )

        for assignment in direct_assignments:
            terminal_id = assignment.transformer_terminal_id
            if not self.alsf.is_ufls_capable(transformer_terminal_id=terminal_id):
                findings.append(
                    Finding(
                        finding_type=FindingType.ALSF_CAPABILITY_ABSENCE,
                        severity=Severity.CRITICAL,
                        source="ufls",
                        description=(
                            "Assigned Transformer Terminal lacks confirmed Automatic Load "
                            "Shedding Functionality capability for UFLS."
                        ),
                        affected_object_type="ufls_direct_assignment",
                        affected_object_id=str(assignment.ufls_direct_assignment_id),
                        scheme_type=SchemeType.UFLS,
                        scheme_version_id=str(version_id),
                        evidence={"transformer_terminal_id": str(terminal_id)},
                    )
                )
            sensitive_facilities = sensitive_by_terminal.get(terminal_id, [])
            if sensitive_facilities:
                findings.append(
                    Finding(
                        finding_type=FindingType.SENSITIVE_CUSTOMER_ASSOCIATION,
                        severity=Severity.CRITICAL,
                        source="ufls",
                        description=(
                            "Assigned Transformer Terminal is associated with "
                            f"{len(sensitive_facilities)} sensitive facility(ies)."
                        ),
                        affected_object_type="ufls_direct_assignment",
                        affected_object_id=str(assignment.ufls_direct_assignment_id),
                        scheme_type=SchemeType.UFLS,
                        scheme_version_id=str(version_id),
                        evidence={
                            "facility_ids": [str(f.id) for f in sensitive_facilities],
                        },
                    )
                )

        for pocket in self.repo.list_pocket_assignments_for_version(version_id):
            opening_points = self.repo.list_opening_points(pocket.ufls_pocket_assignment_id)
            for opening_point in opening_points:
                if not self.alsf.is_ufls_capable(
                    circuit_terminal_id=opening_point.circuit_terminal_id
                ):
                    findings.append(
                        Finding(
                            finding_type=FindingType.ALSF_CAPABILITY_ABSENCE,
                            severity=Severity.CRITICAL,
                            source="ufls",
                            description=(
                                "Boundary Pocket opening point lacks confirmed Automatic Load "
                                "Shedding Functionality capability for UFLS."
                            ),
                            affected_object_type="ufls_pocket_assignment",
                            affected_object_id=str(pocket.ufls_pocket_assignment_id),
                            scheme_type=SchemeType.UFLS,
                            scheme_version_id=str(version_id),
                            evidence={
                                "circuit_terminal_id": str(opening_point.circuit_terminal_id)
                            },
                        )
                    )
        return findings

    # --- Publication prerequisites (task §8) ---------------------------------------------
    def compute_prerequisites(self, version_id: uuid.UUID) -> list[PublicationPrerequisiteResult]:
        """Structural, unconditionally-blocking prerequisites (ADR-015's
        own Publication Prerequisites) — reuses the existing, generic
        `PublicationPrerequisiteResult` contract (Sprint 4); no second
        validator mechanism is introduced (this sprint's own instructions
        §8)."""
        version = self.get_version(version_id)
        results: list[PublicationPrerequisiteResult] = []

        def _result(code: str, passed: bool, description: str) -> PublicationPrerequisiteResult:
            return PublicationPrerequisiteResult(
                prerequisite_code=code,
                passed=passed,
                description=description,
                affected_object_type="ufls_scheme_version",
                affected_object_id=str(version_id),
                source="ufls",
            )

        if version.stage_setting_set_id is None:
            results.append(
                _result("UFLS_STAGE_SETTING_SET_SELECTED", False, "No Stage Setting Set selected.")
            )
        else:
            stage_setting_set = self.stage_setting_registry.get_set(version.stage_setting_set_id)
            results.append(
                _result(
                    "UFLS_STAGE_SETTING_SET_PUBLISHED",
                    stage_setting_set is not None and stage_setting_set.status == "PUBLISHED",
                    "The selected Stage Setting Set must be Published.",
                )
            )

        stages = self.repo.list_stages(version_id)
        results.append(
            _result("UFLS_AT_LEAST_ONE_STAGE", len(stages) > 0, "At least one stage is required.")
        )

        if version.stage_setting_set_id is not None:
            published_settings = self.stage_setting_registry.list_settings(
                version.stage_setting_set_id
            )
            stage_setting_ids = {s.ufls_stage_id: s.stage_setting_id for s in stages}
            missing = {s.stage_setting_id for s in published_settings} - set(
                stage_setting_ids.values()
            )
            results.append(
                _result(
                    "UFLS_STAGE_STRUCTURE_COMPLETE",
                    len(missing) == 0,
                    "Every stage in the selected Stage Setting Set must exist in this version.",
                )
            )

        for stage in stages:
            has_target = stage.target_mw is not None
            has_assignment = bool(
                self.repo.list_direct_assignments_for_stage(stage.ufls_stage_id)
            ) or bool(self.repo.list_pocket_assignments_for_stage(stage.ufls_stage_id))
            results.append(
                PublicationPrerequisiteResult(
                    prerequisite_code="UFLS_STAGE_TARGET_MW_SET",
                    passed=has_target,
                    description=f"Stage '{stage.ufls_stage_id}' must have a target MW.",
                    affected_object_type="ufls_stage",
                    affected_object_id=str(stage.ufls_stage_id),
                    source="ufls",
                )
            )
            results.append(
                PublicationPrerequisiteResult(
                    prerequisite_code="UFLS_STAGE_HAS_ASSIGNMENT",
                    passed=has_assignment,
                    description=f"Stage '{stage.ufls_stage_id}' must have at least one assignment.",
                    affected_object_type="ufls_stage",
                    affected_object_id=str(stage.ufls_stage_id),
                    source="ufls",
                )
            )

        return results

    def get_publication_review(
        self, version_id: uuid.UUID
    ) -> tuple[list[PublicationPrerequisiteResult], list[Finding]]:
        """The read-only "would this publish right now" preview (task
        §8) — never itself a publish action."""
        return self.compute_prerequisites(version_id), self.compute_findings(version_id)

    def publish(
        self,
        version_id: uuid.UUID,
        *,
        publication_event_id: uuid.UUID,
        acknowledgements: list[AcknowledgementInput],
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ):
        """Orchestrates: structural prerequisites + findings (this
        module's own engineering context) -> Publication Treatment
        resolution and `PublicationRecord` creation (Findings and
        Publication Governance, Sprint 4) -> the Scheme Version entity's
        own Draft -> Published transition (`scheme_platform`, this
        sprint). All in one transaction; the caller commits once,
        itself."""
        version = self.get_version(version_id)
        self._require_editable(version)

        prerequisites = self.compute_prerequisites(version_id)
        findings = self.compute_findings(version_id)

        publication_request = PublicationRequest(
            publication_event_id=publication_event_id,
            scheme_type=SchemeType.UFLS,
            scheme_version_id=version_id,
            published_by_user_id=actor_user_id,
            findings=findings,
            prerequisites=prerequisites,
            acknowledgements=acknowledgements,
            topology_version_id=version.topology_version_id,
            load_snapshot_id=version.load_snapshot_id,
            remarks=remarks,
        )
        publication_result = self.publication_record.evaluate_and_record_publication(
            publication_request
        )

        previous_published = self.get_current_published_version(version.scheme_id)
        self.lifecycle.publish(
            version, previous_published=previous_published, actor_user_id=actor_user_id
        )
        self._audit("UflsSchemeVersion", str(version_id), "published", None, None, actor_user_id)
        return publication_result

    # --- Engineering summaries (task §9) -------------------------------------------------
    def get_engineering_summary(self, version_id: uuid.UUID) -> UflsVersionEngineeringSummary:
        stages = self.repo.list_stages(version_id)
        stage_summaries: list[UflsStageMwSummary] = []
        total_target_mw = Decimal("0")
        total_direct = 0
        total_pocket = 0
        substation_ids: set[uuid.UUID] = set()

        for stage in stages:
            direct = self.repo.list_direct_assignments_for_stage(stage.ufls_stage_id)
            pocket = self.repo.list_pocket_assignments_for_stage(stage.ufls_stage_id)
            stage_summaries.append(
                UflsStageMwSummary(
                    ufls_stage_id=stage.ufls_stage_id,
                    stage_order=self.stage_setting_registry.get_setting(
                        stage.stage_setting_id
                    ).stage_order,
                    target_mw=stage.target_mw,
                    direct_assignment_count=len(direct),
                    pocket_assignment_count=len(pocket),
                )
            )
            if stage.target_mw is not None:
                total_target_mw += Decimal(stage.target_mw)
            total_direct += len(direct)
            total_pocket += len(pocket)
            for assignment in direct:
                identity = self.equipment_registry.get_transformer_terminal_identity(
                    assignment.transformer_terminal_id
                )
                if identity is not None:
                    substation_ids.add(identity.substation_id)

        stage_summaries.sort(key=lambda s: s.stage_order)
        findings = self.compute_findings(version_id)

        return UflsVersionEngineeringSummary(
            scheme_version_id=version_id,
            total_target_mw=total_target_mw,
            stage_summaries=stage_summaries,
            direct_assignment_count=total_direct,
            pocket_assignment_count=total_pocket,
            distinct_substation_count=len(substation_ids),
            unresolved_finding_count=len(findings),
            sensitive_customer_finding_count=len(
                [
                    f
                    for f in findings
                    if f.finding_type == FindingType.SENSITIVE_CUSTOMER_ASSOCIATION
                ]
            ),
            alsf_finding_count=len(
                [f for f in findings if f.finding_type == FindingType.ALSF_CAPABILITY_ABSENCE]
            ),
        )

    # --- DTO mapping (CLAUDE.md A6 — API DTOs, never ORM objects, exposed) ------------
    def _resolve_user(self, user_id: uuid.UUID | None):
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    def to_scheme_summary(self, scheme: UflsScheme) -> UflsSchemeSummary:
        published = self.get_current_published_version(scheme.ufls_scheme_id)
        versions = self.list_scheme_versions(scheme.ufls_scheme_id)
        drafts = [
            v for v in versions if v.lifecycle_status == SchemeVersionLifecycleStatus.DRAFT.value
        ]
        latest_draft = max((v.version_number for v in drafts), default=None)
        return UflsSchemeSummary(
            ufls_scheme_id=scheme.ufls_scheme_id,
            name=scheme.name,
            description=scheme.description,
            published_version_number=published.version_number if published else None,
            latest_draft_version_number=latest_draft,
        )

    def to_scheme_detail(self, scheme: UflsScheme) -> UflsSchemeDetail:
        return UflsSchemeDetail(
            ufls_scheme_id=scheme.ufls_scheme_id,
            name=scheme.name,
            description=scheme.description,
            created_at=scheme.created_at,
            updated_at=scheme.updated_at,
        )

    def to_version_summary(self, version: UflsSchemeVersion) -> UflsSchemeVersionSummary:
        return UflsSchemeVersionSummary(
            version_id=version.version_id,
            scheme_id=version.scheme_id,
            ufls_scheme_id=version.scheme_id,
            version_number=version.version_number,
            lifecycle_status=version.lifecycle_status,
            published_at=version.published_at,
            engineering_remarks=version.engineering_remarks,
        )

    def to_version_detail(self, version: UflsSchemeVersion) -> UflsSchemeVersionDetail:
        return UflsSchemeVersionDetail(
            version_id=version.version_id,
            scheme_id=version.scheme_id,
            ufls_scheme_id=version.scheme_id,
            version_number=version.version_number,
            lifecycle_status=version.lifecycle_status,
            published_at=version.published_at,
            published_by=self._resolve_user(version.published_by_user_id),
            superseded_at=version.superseded_at,
            entered_in_error_at=version.entered_in_error_at,
            entered_in_error_by=self._resolve_user(version.entered_in_error_by_user_id),
            entered_in_error_reason=version.entered_in_error_reason,
            engineering_remarks=version.engineering_remarks,
            created_at=version.created_at,
            updated_at=version.updated_at,
            stage_setting_set_id=version.stage_setting_set_id,
            study_reference=version.study_reference,
            effective_date=version.effective_date,
            topology_version_id=version.topology_version_id,
            load_snapshot_id=version.load_snapshot_id,
        )

    def to_stage_detail(self, stage: UflsStage) -> UflsStageDetail:
        setting = self.stage_setting_registry.get_setting(stage.stage_setting_id)
        direct = self.repo.list_direct_assignments_for_stage(stage.ufls_stage_id)
        pocket = self.repo.list_pocket_assignments_for_stage(stage.ufls_stage_id)
        return UflsStageDetail(
            ufls_stage_id=stage.ufls_stage_id,
            scheme_version_id=stage.scheme_version_id,
            stage_setting_id=stage.stage_setting_id,
            stage_order=setting.stage_order,
            triggers=[
                UflsStageTriggerSummary(
                    stage_setting_trigger_id=t.stage_setting_trigger_id,
                    trigger_order=t.trigger_order,
                    threshold_value=t.threshold_value,
                    threshold_unit=t.threshold_unit,
                    time_delay_ms=t.time_delay_ms,
                )
                for t in setting.triggers
            ],
            target_mw=stage.target_mw,
            engineering_remarks=stage.engineering_remarks,
            direct_assignment_count=len(direct),
            pocket_assignment_count=len(pocket),
        )

    def to_direct_assignment_detail(
        self, assignment: UflsDirectAssignment
    ) -> UflsDirectAssignmentDetail:
        identity = self.equipment_registry.get_transformer_terminal_identity(
            assignment.transformer_terminal_id
        )
        return UflsDirectAssignmentDetail(
            ufls_direct_assignment_id=assignment.ufls_direct_assignment_id,
            ufls_stage_id=assignment.ufls_stage_id,
            transformer_terminal_id=assignment.transformer_terminal_id,
            substation_id=identity.substation_id,
            substation_mnemonic=identity.substation_mnemonic,
            remarks=assignment.remarks,
            created_at=assignment.created_at,
        )

    def to_pocket_assignment_detail(
        self, assignment: UflsPocketAssignment
    ) -> UflsPocketAssignmentDetail:
        opening_points = self.repo.list_opening_points(assignment.ufls_pocket_assignment_id)
        return UflsPocketAssignmentDetail(
            ufls_pocket_assignment_id=assignment.ufls_pocket_assignment_id,
            ufls_stage_id=assignment.ufls_stage_id,
            circuit_terminal_ids=[op.circuit_terminal_id for op in opening_points],
            remarks=assignment.remarks,
            created_at=assignment.created_at,
        )

    def to_publication_review_result(self, version_id: uuid.UUID) -> PublicationReviewResult:
        prerequisites, findings = self.get_publication_review(version_id)
        return PublicationReviewResult(
            scheme_version_id=version_id,
            prerequisites=[
                PublicationPrerequisiteSummary(
                    prerequisite_code=p.prerequisite_code,
                    passed=p.passed,
                    description=p.description,
                    affected_object_type=p.affected_object_type,
                    affected_object_id=p.affected_object_id,
                )
                for p in prerequisites
            ],
            all_prerequisites_passed=all(p.passed for p in prerequisites),
            findings=[f.model_dump(mode="json") for f in findings],
        )

    def to_publish_result(self, publication_result) -> PublishResult:
        return PublishResult(
            publication_record_id=publication_result.publication_record_id,
            scheme_version_id=publication_result.scheme_version_id,
            published_at=publication_result.published_at,
            finding_count=publication_result.finding_count,
            acknowledgement_count=publication_result.acknowledgement_count,
        )

    # --- Platform events (task §10) --------------------------------------------------
    def _notify_change(self, *, entity_type: str, entity_id: uuid.UUID, action: str) -> None:
        """Publishes a `ufls.<entity_type>.<action>` `ChangeDescriptor`
        for a meaningful engineering change that is not itself a Scheme
        Version lifecycle transition (those are already published by
        `scheme_platform.SchemeVersionLifecycleService` internally, via
        `self.lifecycle`). Carries only stable identifiers — never a
        duplicated copy of registry/operational payload data (this
        sprint's own instructions §10). Currently resolves to zero
        affected targets in production (`ContinuousEvaluationService`'s
        own default `NullAffectedSchemeResolver` — no real
        `AffectedSchemeResolver` is wired anywhere in this codebase yet,
        a pre-existing Sprint 6 gap, not introduced here); still called
        unconditionally so the event is emitted the moment a real
        resolver is composed in, with no further UFLS-side change."""
        descriptor = ChangeDescriptor(
            descriptor=f"ufls.{entity_type}.{action}",
            source_module="ufls",
            source_entity_type=entity_type,
            source_entity_id=str(entity_id),
            occurred_at=datetime.now(UTC),
        )
        self.continuous_evaluation.notify_source_data_changed(descriptor)

    # --- Audit ----------------------------------------------------------------------
    def _audit(
        self,
        entity_type: str,
        entity_id: str,
        field_name: str,
        old_value: str | None,
        new_value: str | None,
        actor_user_id: uuid.UUID | None,
        *,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_entry(
            UflsAuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )
