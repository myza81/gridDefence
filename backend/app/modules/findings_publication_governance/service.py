"""Findings and Publication Governance service layer (CLAUDE.md §14) —
business rules, transactions, orchestration, and audit writing live here,
and only here (CLAUDE.md A1: this module's own tables are written to
exclusively by this layer).

**Policy resolution precedence** (module document §4, §4.2; ADR-018's own
central rule: "Publication treatment is resolved through this shared
policy layer, never through bespoke logic in individual detectors or
scheme modules"). Every `PublicationTreatmentPolicy` row is keyed by
`severity` (always) plus two independently-optional narrowing dimensions,
`finding_type` and `scheme_type`. Four precedence levels, most specific
first:

    1. scheme-specific + finding-type override   (severity, finding_type, scheme_type)
    2. global finding-type override              (severity, finding_type, None)
    3. scheme-specific severity override         (severity, None, scheme_type)
    4. global severity baseline                  (severity, None, None)

This order is derived from module document §4's own description of the
two dimensions' relative roles, not assumed: §4 describes the
finding-type axis as the *primary* key ("Global default **per finding
type**... Optional scheme-specific override — narrows or widens **the
default**"), with `scheme_type` explicitly framed as a *secondary* lever
that narrows or widens whatever finding-type-level default already
applies. Ranking finding-type specificity above scheme-type specificity
when the two would otherwise tie (level 2 above level 3) is a direct
consequence of that stated primacy, not an arbitrary tie-break.

Only level 4 is ever populated by this sprint's own bootstrap (module
document §4.2 — the four severity-keyed baseline rows); levels 1-3 exist
so a future administrator can add a finding-type or scheme-specific
override *without any schema change*, exactly as this sprint's own
instructions require. No detector or finding-type-specific override is
seeded speculatively.

`resolve_publication_treatment` never falls back to a hardcoded treatment
outside this table — if no row matches even the global severity baseline
(only possible if bootstrap has never run), it raises
`NoApplicablePolicyError` rather than silently guessing (this sprint's
own instructions §7).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.findings_publication_governance.exceptions import (
    AcknowledgementForNonAcknowledgeableFindingError,
    CannotRemoveBaselinePolicyError,
    ChangeReasonRequiredError,
    DuplicateAcknowledgementError,
    DuplicatePolicyError,
    DuplicatePublicationEventError,
    InvalidFindingTypeError,
    InvalidSchemeTypeError,
    InvalidSeverityError,
    InvalidTreatmentError,
    MissingAcknowledgementError,
    MissingAcknowledgementJustificationError,
    NoApplicablePolicyError,
    PolicyNotFoundError,
    PrerequisiteFailedError,
    PublicationBlockedByFindingError,
    UnknownAcknowledgementTargetError,
)
from app.modules.findings_publication_governance.findings import (
    Finding,
    FindingType,
    SchemeType,
    Severity,
)
from app.modules.findings_publication_governance.models import (
    PublicationRecord,
    PublicationRecordAcknowledgement,
    PublicationRecordFinding,
    PublicationRecordPrerequisite,
    PublicationTreatment,
    PublicationTreatmentPolicy,
    PublicationTreatmentPolicyAuditLog,
)
from app.modules.findings_publication_governance.publication import (
    PublicationPrerequisiteResult,
    PublicationRequest,
    PublicationResult,
)
from app.modules.findings_publication_governance.repository import (
    PublicationRecordRepository,
    PublicationTreatmentPolicyRepository,
)
from app.modules.findings_publication_governance.schemas import (
    FrozenAcknowledgementEvidence,
    FrozenFindingEvidence,
    FrozenPrerequisiteEvidence,
    PolicyAuditLogEntry,
    PolicyDetail,
    PublicationRecordDetail,
    PublicationRecordSummary,
)
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService

_SEVERITY_VALUES = {s.value for s in Severity}
_FINDING_TYPE_VALUES = {f.value for f in FindingType}
_SCHEME_TYPE_VALUES = {s.value for s in SchemeType}
_TREATMENT_VALUES = {t.value for t in PublicationTreatment}


@dataclass(frozen=True)
class ResolvedTreatment:
    """The matched policy's own key and identity, not merely the bare
    treatment value — see `resolve_publication_treatment_with_policy`'s
    own docstring for why Sprint 4's publication evidence needs this
    richer shape."""

    treatment: str
    matched_policy_id: uuid.UUID
    matched_policy_severity: str
    matched_policy_finding_type: str | None
    matched_policy_scheme_type: str | None


class PublicationTreatmentPolicyService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PublicationTreatmentPolicyRepository(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _audit(
        self,
        *,
        policy_id: uuid.UUID | None,
        severity: str,
        finding_type: str | None,
        scheme_type: str | None,
        action: str,
        old_value: str | None,
        new_value: str | None,
        actor_user_id: uuid.UUID | None,
        change_reason: str | None,
    ) -> None:
        self.repo.add_audit_log(
            PublicationTreatmentPolicyAuditLog(
                policy_id=policy_id,
                severity=severity,
                finding_type=finding_type,
                scheme_type=scheme_type,
                action=action,
                old_value=old_value,
                new_value=new_value,
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _resolve_user(self, user_id: uuid.UUID | None) -> UserSummary | None:
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    def _require_reason(self, change_reason: str | None) -> str:
        if not change_reason or not change_reason.strip():
            raise ChangeReasonRequiredError()
        return change_reason

    def _validate_severity(self, severity: str) -> None:
        if severity not in _SEVERITY_VALUES:
            raise InvalidSeverityError(severity)

    def _validate_finding_type(self, finding_type: str | None) -> None:
        if finding_type is not None and finding_type not in _FINDING_TYPE_VALUES:
            raise InvalidFindingTypeError(finding_type)

    def _validate_scheme_type(self, scheme_type: str | None) -> None:
        if scheme_type is not None and scheme_type not in _SCHEME_TYPE_VALUES:
            raise InvalidSchemeTypeError(scheme_type)

    def _validate_treatment(self, treatment: str) -> None:
        if treatment not in _TREATMENT_VALUES:
            raise InvalidTreatmentError(treatment)

    def _to_detail(self, policy: PublicationTreatmentPolicy) -> PolicyDetail:
        return PolicyDetail(
            policy_id=policy.policy_id,
            severity=policy.severity,
            finding_type=policy.finding_type,
            scheme_type=policy.scheme_type,
            treatment=policy.treatment,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
            created_by=self._resolve_user(policy.created_by_user_id),
            updated_by=self._resolve_user(policy.updated_by_user_id),
        )

    @staticmethod
    def _is_baseline(policy: PublicationTreatmentPolicy) -> bool:
        return policy.finding_type is None and policy.scheme_type is None

    # --- Mutation (governed methods only — CLAUDE.md A1, no unrestricted CRUD) --
    def create_policy(
        self,
        *,
        severity: str,
        finding_type: str | None,
        scheme_type: str | None,
        treatment: str,
        change_reason: str,
        actor_user_id: uuid.UUID | None,
    ) -> PublicationTreatmentPolicy:
        self._validate_severity(severity)
        self._validate_finding_type(finding_type)
        self._validate_scheme_type(scheme_type)
        self._validate_treatment(treatment)
        change_reason = self._require_reason(change_reason)

        if self.repo.find_policy(
            severity=severity, finding_type=finding_type, scheme_type=scheme_type
        ):
            raise DuplicatePolicyError(severity, finding_type, scheme_type)

        policy = self.repo.add(
            PublicationTreatmentPolicy(
                policy_id=uuid.uuid4(),
                severity=severity,
                finding_type=finding_type,
                scheme_type=scheme_type,
                treatment=treatment,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        self._audit(
            policy_id=policy.policy_id,
            severity=severity,
            finding_type=finding_type,
            scheme_type=scheme_type,
            action="created",
            old_value=None,
            new_value=treatment,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return policy

    def update_treatment(
        self,
        policy_id: uuid.UUID,
        *,
        treatment: str,
        change_reason: str,
        actor_user_id: uuid.UUID | None,
    ) -> PublicationTreatmentPolicy:
        policy = self.repo.get_by_id(policy_id)
        if policy is None:
            raise PolicyNotFoundError(policy_id)
        self._validate_treatment(treatment)
        change_reason = self._require_reason(change_reason)

        if treatment == policy.treatment:
            # No-op: this sprint's own instructions §11 — changing a policy
            # to the same effective value must not create redundant audit
            # noise.
            return policy

        self._audit(
            policy_id=policy.policy_id,
            severity=policy.severity,
            finding_type=policy.finding_type,
            scheme_type=policy.scheme_type,
            action="treatment_changed",
            old_value=policy.treatment,
            new_value=treatment,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        policy.treatment = treatment
        policy.updated_by_user_id = actor_user_id
        self.db.flush()
        return policy

    def remove_policy(
        self, policy_id: uuid.UUID, *, change_reason: str, actor_user_id: uuid.UUID | None
    ) -> None:
        policy = self.repo.get_by_id(policy_id)
        if policy is None:
            raise PolicyNotFoundError(policy_id)
        if self._is_baseline(policy):
            raise CannotRemoveBaselinePolicyError(policy_id)
        change_reason = self._require_reason(change_reason)

        self._audit(
            policy_id=policy.policy_id,
            severity=policy.severity,
            finding_type=policy.finding_type,
            scheme_type=policy.scheme_type,
            action="removed",
            old_value=policy.treatment,
            new_value=None,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        self.repo.delete(policy)

    # --- Read ---------------------------------------------------------------------
    def get_policy(self, policy_id: uuid.UUID) -> PolicyDetail | None:
        policy = self.repo.get_by_id(policy_id)
        return self._to_detail(policy) if policy else None

    def list_policies(
        self,
        *,
        severity: str | None = None,
        finding_type: str | None = None,
        scheme_type: str | None = None,
        treatment: str | None = None,
    ) -> list[PolicyDetail]:
        policies = self.repo.list_all(
            severity=severity,
            finding_type=finding_type,
            scheme_type=scheme_type,
            treatment=treatment,
        )
        return [self._to_detail(p) for p in policies]

    def list_audit_log(
        self, policy_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[PolicyAuditLogEntry], int]:
        items, total = self.repo.list_audit_log(
            policy_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            PolicyAuditLogEntry(
                log_id=e.log_id,
                policy_id=e.policy_id,
                severity=e.severity,
                finding_type=e.finding_type,
                scheme_type=e.scheme_type,
                action=e.action,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total

    # --- Public service interface for future consumers (ADR-018 §11) -----------
    def resolve_publication_treatment_with_policy(
        self, finding: Finding, scheme_type: str | None = None
    ) -> ResolvedTreatment:
        """The one shared resolution path every future caller (the
        Continuous Evaluation Engine, a scheme module, and — from Sprint
        4 — the publication orchestration service below) must use — never
        a bespoke, per-detector gating decision (ADR-018's own central
        rule). `scheme_type` is an explicit override for callers that
        already know the scheme context; if omitted, falls back to
        `finding.scheme_type` (the Finding's own optional context field).
        See module docstring for the full four-level precedence order and
        its derivation.

        Returns the *matched policy's own key and identity*, not merely
        the bare treatment string — Sprint 4's own publication evidence
        (models.py's `PublicationRecordFinding`) must freeze which policy,
        and at what precedence level, actually applied (this sprint's own
        instructions §9), so a later policy change or removal never makes
        a historical `PublicationRecord` uninterpretable."""
        severity = finding.severity.value
        finding_type = finding.finding_type.value
        effective_scheme_type = scheme_type or (
            finding.scheme_type.value if finding.scheme_type else None
        )

        lookups: list[tuple[str, str | None, str | None]] = []
        if effective_scheme_type is not None:
            lookups.append((severity, finding_type, effective_scheme_type))
        lookups.append((severity, finding_type, None))
        if effective_scheme_type is not None:
            lookups.append((severity, None, effective_scheme_type))
        lookups.append((severity, None, None))

        for lookup_severity, lookup_finding_type, lookup_scheme_type in lookups:
            policy = self.repo.find_policy(
                severity=lookup_severity,
                finding_type=lookup_finding_type,
                scheme_type=lookup_scheme_type,
            )
            if policy is not None:
                return ResolvedTreatment(
                    treatment=policy.treatment,
                    matched_policy_id=policy.policy_id,
                    matched_policy_severity=policy.severity,
                    matched_policy_finding_type=policy.finding_type,
                    matched_policy_scheme_type=policy.scheme_type,
                )

        raise NoApplicablePolicyError(severity)

    def resolve_publication_treatment(
        self, finding: Finding, scheme_type: str | None = None
    ) -> str:
        """Unchanged from Sprint 3 — same signature, same exceptions,
        same return value (a bare treatment string) for every existing
        caller. Now implemented as a thin wrapper over
        `resolve_publication_treatment_with_policy`, which performs the
        identical four-level lookup; this is a behaviour-preserving
        refactor, not a new resolution path."""
        return self.resolve_publication_treatment_with_policy(
            finding, scheme_type=scheme_type
        ).treatment

    def resolve_publication_treatments(
        self, findings: list[Finding], scheme_type: str | None = None
    ) -> list[tuple[Finding, str]]:
        """Batch convenience over `resolve_publication_treatment` — a
        future caller with many findings from one evaluation pass should
        not need to loop and re-derive precedence itself. Purely a thin
        wrapper; no new resolution logic."""
        return [
            (finding, self.resolve_publication_treatment(finding, scheme_type=scheme_type))
            for finding in findings
        ]


class PublicationRecordService:
    """Publication-orchestration and PublicationRecord-evidence service
    (this sprint's own instructions §8, §16) — composes
    `PublicationTreatmentPolicyService` (Sprint 3) rather than
    duplicating policy-resolution logic.

    **Concurrency / duplicate-publication-event identity** (this sprint's
    own instructions §12): the chosen, documented approach is a
    caller-supplied `publication_event_id` (UUID) — a per-attempt
    idempotency key, not a scheme-lifecycle sequence number. This module
    has no visibility into any scheme module's own version-history
    sequencing (no `scheme_version` table exists, and none ever will —
    this sprint's own instructions §3), so "scheme type + scheme-version
    ID + publication sequence" (the alternative this sprint's own
    instructions mention) is not an identifier this module could compute
    or verify itself. A caller-supplied event id is the narrowest
    mechanism that prevents duplicate recording without inventing scheme
    lifecycle behaviour: the same retried attempt (same event id) is
    rejected deterministically (`DuplicatePublicationEventError`) via this
    table's own database-level `UNIQUE` constraint
    (`uq_publication_record_event`, models.py) — not a distributed lock,
    not Redis, just an ordinary unique index checked (defensively, in
    Python, before any other work) and enforced (authoritatively, by the
    database) on every attempt.

    **Transaction boundary** (this sprint's own instructions §8): neither
    this method nor any repository method it calls ever calls
    `self.db.commit()` — only `flush()`, exactly like every other
    service in this codebase. A future scheme service calls
    `evaluate_and_record_publication` *within its own transaction*,
    alongside its own Scheme Version transition and supersession logic,
    and commits once, itself, when both halves succeed. If this method
    raises, the caller's own transaction is left uncommitted and can be
    rolled back as a whole — this service never partially commits.

    **Publication orchestration algorithm** (this sprint's own
    instructions §8, followed in this exact order):
    1. Validate the request structurally (acknowledgement bounds,
       duplicates, non-empty justification — policy-independent checks).
    2. Reject a duplicate `publication_event_id`.
    3. Confirm every supplied structural prerequisite passed.
    4. Resolve Publication Treatment Policy for every Finding (Sprint 3's
       `resolve_publication_treatment_with_policy`).
    5. Reject if any Finding resolved to `BLOCK`.
    6. Determine which findings require acknowledgement
       (`ALLOW_WITH_ACKNOWLEDGEMENT`).
    7. Verify acknowledgement evidence corresponds exactly to those
       findings — none missing, none unnecessary.
    8. Freeze the complete evidence into new ORM rows.
    9. Insert the aggregate (flush, never commit).
    10. Return a stable `PublicationResult`.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PublicationRecordRepository(db)
        self.policy_service = PublicationTreatmentPolicyService(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _resolve_user(self, user_id: uuid.UUID | None) -> UserSummary | None:
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    def _validate_request(self, request: PublicationRequest) -> None:
        """Structural, policy-independent checks only — step 1 of the
        algorithm. Semantic acknowledgement-vs-resolved-treatment checks
        happen later, in `_validate_acknowledgements`, once policy
        resolution (step 4) is known."""
        finding_count = len(request.findings)
        seen_indexes: set[int] = set()
        for acknowledgement in request.acknowledgements:
            if not (0 <= acknowledgement.finding_index < finding_count):
                raise UnknownAcknowledgementTargetError(acknowledgement.finding_index)
            if acknowledgement.finding_index in seen_indexes:
                raise DuplicateAcknowledgementError(acknowledgement.finding_index)
            seen_indexes.add(acknowledgement.finding_index)
            if not acknowledgement.justification or not acknowledgement.justification.strip():
                raise MissingAcknowledgementJustificationError(acknowledgement.finding_index)

    @staticmethod
    def _prerequisite_evidence_dict(
        prerequisite: PublicationPrerequisiteResult,
    ) -> dict[str, object]:
        return {
            "prerequisite_code": prerequisite.prerequisite_code,
            "description": prerequisite.description,
            "affected_object_type": prerequisite.affected_object_type,
            "affected_object_id": prerequisite.affected_object_id,
            "source": prerequisite.source,
        }

    @staticmethod
    def _finding_evidence_dict(
        index: int, finding: Finding, resolved: ResolvedTreatment
    ) -> dict[str, object]:
        return {
            "finding_index": index,
            "finding_type": finding.finding_type.value,
            "severity": finding.severity.value,
            "description": finding.description,
            "affected_object_type": finding.affected_object_type,
            "affected_object_id": finding.affected_object_id,
            "resolved_treatment": resolved.treatment,
        }

    def _validate_acknowledgements(
        self,
        request: PublicationRequest,
        resolved: list[tuple[Finding, ResolvedTreatment]],
    ) -> None:
        """Steps 6-7 — semantic checks, once policy resolution is known.
        `_validate_request` already confirmed every acknowledgement's
        `finding_index` is in-bounds and unique, and every justification
        is non-empty."""
        ack_required_indexes = {
            index
            for index, (_finding, treatment) in enumerate(resolved)
            if treatment.treatment == PublicationTreatment.ALLOW_WITH_ACKNOWLEDGEMENT.value
        }
        ack_by_index = {ack.finding_index: ack for ack in request.acknowledgements}

        missing = sorted(ack_required_indexes - ack_by_index.keys())
        if missing:
            raise MissingAcknowledgementError(missing)

        for index, _acknowledgement in ack_by_index.items():
            if index not in ack_required_indexes:
                raise AcknowledgementForNonAcknowledgeableFindingError(
                    index, resolved[index][1].treatment
                )

    # --- Publication orchestration (the shared, single entry point) ------------
    def evaluate_and_record_publication(self, request: PublicationRequest) -> PublicationResult:
        # 1. Validate the publication request structurally.
        self._validate_request(request)

        # 2. Reject a duplicate publication event (idempotency key).
        if self.repo.get_by_event_id(request.publication_event_id) is not None:
            raise DuplicatePublicationEventError(request.publication_event_id)

        # 3. Confirm all supplied scheme-specific prerequisites pass.
        prerequisites = list(request.prerequisites)
        failed = [
            self._prerequisite_evidence_dict(prerequisite)
            for prerequisite in prerequisites
            if not prerequisite.passed
        ]
        if failed:
            raise PrerequisiteFailedError(failed)

        # 4. Resolve Publication Treatment Policy for every Finding.
        findings = list(request.findings)
        resolved: list[tuple[Finding, ResolvedTreatment]] = [
            (
                finding,
                self.policy_service.resolve_publication_treatment_with_policy(
                    finding, scheme_type=request.scheme_type.value
                ),
            )
            for finding in findings
        ]

        # 5. Reject publication if any Finding resolves to Block.
        blocked = [
            self._finding_evidence_dict(index, finding, treatment)
            for index, (finding, treatment) in enumerate(resolved)
            if treatment.treatment == PublicationTreatment.BLOCK.value
        ]
        if blocked:
            raise PublicationBlockedByFindingError(blocked)

        # 6-7. Require and verify acknowledgement evidence.
        self._validate_acknowledgements(request, resolved)

        # 8. Freeze the complete evidence into new ORM rows (not yet persisted).
        ack_required_indexes = {
            index
            for index, (_finding, treatment) in enumerate(resolved)
            if treatment.treatment == PublicationTreatment.ALLOW_WITH_ACKNOWLEDGEMENT.value
        }
        record = PublicationRecord(
            publication_record_id=uuid.uuid4(),
            publication_event_id=request.publication_event_id,
            scheme_type=request.scheme_type.value,
            scheme_version_id=request.scheme_version_id,
            published_by_user_id=request.published_by_user_id,
            topology_version_id=request.topology_version_id,
            load_snapshot_id=request.load_snapshot_id,
            remarks=request.remarks,
        )
        finding_rows = [
            PublicationRecordFinding(
                publication_record_finding_id=uuid.uuid4(),
                finding_index=index,
                finding_type=finding.finding_type.value,
                severity=finding.severity.value,
                source=finding.source,
                description=finding.description,
                affected_object_type=finding.affected_object_type,
                affected_object_id=finding.affected_object_id,
                evidence=finding.evidence,
                resolved_treatment=treatment.treatment,
                matched_policy_id=treatment.matched_policy_id,
                matched_policy_severity=treatment.matched_policy_severity,
                matched_policy_finding_type=treatment.matched_policy_finding_type,
                matched_policy_scheme_type=treatment.matched_policy_scheme_type,
                acknowledgement_required=(index in ack_required_indexes),
            )
            for index, (finding, treatment) in enumerate(resolved)
        ]
        prerequisite_rows = [
            PublicationRecordPrerequisite(
                publication_record_prerequisite_id=uuid.uuid4(),
                prerequisite_index=index,
                prerequisite_code=prerequisite.prerequisite_code,
                passed=prerequisite.passed,
                description=prerequisite.description,
                affected_object_type=prerequisite.affected_object_type,
                affected_object_id=prerequisite.affected_object_id,
                evidence=prerequisite.evidence,
                source=prerequisite.source,
            )
            for index, prerequisite in enumerate(prerequisites)
        ]
        acknowledgement_rows = [
            PublicationRecordAcknowledgement(
                publication_record_acknowledgement_id=uuid.uuid4(),
                finding_index=acknowledgement.finding_index,
                acknowledged_by_user_id=acknowledgement.acknowledged_by_user_id,
                acknowledged_at=acknowledgement.acknowledged_at or datetime.now(UTC),
                justification=acknowledgement.justification,
            )
            for acknowledgement in request.acknowledgements
        ]

        # 9. Insert the aggregate — flush only, never commit (see class docstring).
        self.repo.add_aggregate(
            record,
            findings=finding_rows,
            prerequisites=prerequisite_rows,
            acknowledgements=acknowledgement_rows,
        )

        # 10. Return a stable publication result DTO.
        return PublicationResult(
            publication_record_id=record.publication_record_id,
            scheme_type=request.scheme_type,
            scheme_version_id=request.scheme_version_id,
            published_at=record.published_at,
            finding_count=len(finding_rows),
            acknowledgement_count=len(acknowledgement_rows),
        )

    # --- Read (immutable evidence) ------------------------------------------------
    def get_publication_record(
        self, publication_record_id: uuid.UUID
    ) -> PublicationRecordDetail | None:
        record = self.repo.get_by_id(publication_record_id)
        if record is None:
            return None

        findings = self.repo.list_findings(publication_record_id)
        prerequisites = self.repo.list_prerequisites(publication_record_id)
        acknowledgements = self.repo.list_acknowledgements(publication_record_id)

        return PublicationRecordDetail(
            publication_record_id=record.publication_record_id,
            publication_event_id=record.publication_event_id,
            scheme_type=record.scheme_type,
            scheme_version_id=record.scheme_version_id,
            published_by=self._resolve_user(record.published_by_user_id),
            published_at=record.published_at,
            topology_version_id=record.topology_version_id,
            load_snapshot_id=record.load_snapshot_id,
            remarks=record.remarks,
            evidence_schema_version=record.evidence_schema_version,
            findings=[
                FrozenFindingEvidence(
                    finding_index=f.finding_index,
                    finding_type=f.finding_type,
                    severity=f.severity,
                    source=f.source,
                    description=f.description,
                    affected_object_type=f.affected_object_type,
                    affected_object_id=f.affected_object_id,
                    evidence=f.evidence,
                    resolved_treatment=f.resolved_treatment,
                    matched_policy_id=f.matched_policy_id,
                    matched_policy_severity=f.matched_policy_severity,
                    matched_policy_finding_type=f.matched_policy_finding_type,
                    matched_policy_scheme_type=f.matched_policy_scheme_type,
                    acknowledgement_required=f.acknowledgement_required,
                )
                for f in findings
            ],
            prerequisites=[
                FrozenPrerequisiteEvidence(
                    prerequisite_index=p.prerequisite_index,
                    prerequisite_code=p.prerequisite_code,
                    passed=p.passed,
                    description=p.description,
                    affected_object_type=p.affected_object_type,
                    affected_object_id=p.affected_object_id,
                    evidence=p.evidence,
                    source=p.source,
                )
                for p in prerequisites
            ],
            acknowledgements=[
                FrozenAcknowledgementEvidence(
                    finding_index=a.finding_index,
                    acknowledged_by=self._resolve_user(a.acknowledged_by_user_id),
                    acknowledged_at=a.acknowledged_at,
                    justification=a.justification,
                )
                for a in acknowledgements
            ],
        )

    def list_publication_records(
        self,
        *,
        scheme_type: str | None = None,
        scheme_version_id: uuid.UUID | None = None,
        page: int,
        page_size: int,
    ) -> tuple[list[PublicationRecordSummary], int]:
        records, total = self.repo.list_all(
            scheme_type=scheme_type,
            scheme_version_id=scheme_version_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        summaries = [
            PublicationRecordSummary(
                publication_record_id=record.publication_record_id,
                scheme_type=record.scheme_type,
                scheme_version_id=record.scheme_version_id,
                published_at=record.published_at,
                finding_count=len(self.repo.list_findings(record.publication_record_id)),
            )
            for record in records
        ]
        return summaries, total
