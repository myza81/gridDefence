"""Findings and Publication Governance business errors (CLAUDE.md A9 —
structured, not ad hoc)."""

from __future__ import annotations

from app.shared.exceptions import AppError, NotFoundError, ValidationAppError

__all__ = [
    "AppError",
    "NotFoundError",
    "ValidationAppError",
    "PolicyNotFoundError",
    "InvalidSeverityError",
    "InvalidFindingTypeError",
    "InvalidSchemeTypeError",
    "InvalidTreatmentError",
    "ChangeReasonRequiredError",
    "DuplicatePolicyError",
    "CannotRemoveBaselinePolicyError",
    "CannotChangePolicyKeyError",
    "NoApplicablePolicyError",
    "InvalidPublicationRequestError",
    "PrerequisiteFailedError",
    "PublicationBlockedByFindingError",
    "MissingAcknowledgementError",
    "DuplicateAcknowledgementError",
    "AcknowledgementForNonAcknowledgeableFindingError",
    "UnknownAcknowledgementTargetError",
    "MissingAcknowledgementJustificationError",
    "DuplicatePublicationEventError",
    "PublicationRecordNotFoundError",
]


class PolicyNotFoundError(NotFoundError):
    def __init__(self, policy_id: object) -> None:
        super().__init__(f"Publication Treatment Policy '{policy_id}' not found.")


class InvalidSeverityError(ValidationAppError):
    def __init__(self, severity: str) -> None:
        super().__init__(
            f"Unsupported severity '{severity}' — must be one of INFORMATION, ADVISORY, "
            "WARNING, CRITICAL (findings-and-publication-governance-architecture.md §3)."
        )


class InvalidFindingTypeError(ValidationAppError):
    def __init__(self, finding_type: str) -> None:
        super().__init__(
            f"Unsupported finding_type '{finding_type}' — not one of the finding-source "
            "categories named by the finalized architecture "
            "(findings-and-publication-governance-architecture.md §3)."
        )


class InvalidSchemeTypeError(ValidationAppError):
    def __init__(self, scheme_type: str) -> None:
        super().__init__(
            f"Unsupported scheme_type '{scheme_type}' — must be one of UFLS, UVLS, EMLS."
        )


class InvalidTreatmentError(ValidationAppError):
    def __init__(self, treatment: str) -> None:
        super().__init__(
            f"Unsupported treatment '{treatment}' — must be one of BLOCK, "
            "ALLOW_WITH_ACKNOWLEDGEMENT, ALLOW_WITHOUT_ACKNOWLEDGEMENT "
            "(findings-and-publication-governance-architecture.md §4)."
        )


class ChangeReasonRequiredError(ValidationAppError):
    def __init__(self) -> None:
        super().__init__(
            "A non-empty change_reason is required for every Publication Treatment Policy "
            "mutation (findings-and-publication-governance-architecture.md §4)."
        )


class DuplicatePolicyError(ValidationAppError):
    """A policy already exists at this exact (severity, finding_type,
    scheme_type) precedence key — module document §4/§4.2; this sprint's
    own instructions §15 ("duplicate policy identity", "shadowed or
    duplicated at the same specificity")."""

    def __init__(self, severity: str, finding_type: str | None, scheme_type: str | None) -> None:
        super().__init__(
            f"A Publication Treatment Policy already exists for severity={severity}, "
            f"finding_type={finding_type}, scheme_type={scheme_type} — update the existing "
            "policy instead of creating a duplicate."
        )


class CannotRemoveBaselinePolicyError(ValidationAppError):
    """The four global severity baselines (finding_type and scheme_type
    both NULL) are protected — removing one could leave a supported
    severity with no resolvable treatment (this sprint's own instructions
    §9)."""

    def __init__(self, policy_id: object) -> None:
        super().__init__(
            f"Publication Treatment Policy '{policy_id}' is a required global severity "
            "baseline and cannot be removed — its treatment value may be changed, but the "
            "baseline itself must always exist so every severity always resolves to a "
            "treatment."
        )


class CannotChangePolicyKeyError(ValidationAppError):
    """`severity`/`finding_type`/`scheme_type` identify *which* policy this
    is — changing them would make this a different policy, not an edit of
    this one. Only `treatment` may be updated."""

    def __init__(self) -> None:
        super().__init__(
            "severity, finding_type, and scheme_type are immutable once a policy is created — "
            "only its treatment may be changed. Remove this policy and create a new one instead."
        )


class NoApplicablePolicyError(ValidationAppError):
    """This sprint's own instructions §7: "explicit error behavior if no
    applicable policy exists... no silent fallback to hardcoded behavior
    outside the seeded baseline." Should only occur if bootstrap has never
    run — every supported severity is guaranteed a baseline once it has."""

    def __init__(self, severity: str) -> None:
        super().__init__(
            f"No Publication Treatment Policy resolves for severity={severity} — the global "
            "severity baseline is missing. Run this module's bootstrap "
            "(python -m app.modules.findings_publication_governance.bootstrap) to seed it."
        )


class InvalidPublicationRequestError(ValidationAppError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"Invalid publication request: {reason}")


class PrerequisiteFailedError(ValidationAppError):
    """Module document §5: a failed structural publication prerequisite
    unconditionally blocks publication — never a finding, never
    configurable. Carries every failed prerequisite (not merely the
    first) so a future scheme UI can show them all at once (this sprint's
    own instructions §17)."""

    def __init__(self, failed: list[dict[str, object]]) -> None:
        codes = ", ".join(str(f["prerequisite_code"]) for f in failed)
        super().__init__(
            f"Publication blocked — {len(failed)} structural prerequisite(s) failed: {codes}."
        )
        self.failed_prerequisites = failed


class PublicationBlockedByFindingError(ValidationAppError):
    """ADR-018 §7: a finding resolving to `Block` treatment blocks
    Publication until corrected or the applicable policy is changed.
    Carries every blocking finding (this sprint's own instructions §17)."""

    def __init__(self, blocked: list[dict[str, object]]) -> None:
        super().__init__(
            f"Publication blocked — {len(blocked)} finding(s) resolved to BLOCK treatment."
        )
        self.blocked_findings = blocked


class MissingAcknowledgementError(ValidationAppError):
    """Module document §6: every finding resolving to `Allow with
    acknowledgement` must be acknowledged before Publish proceeds."""

    def __init__(self, missing_finding_indexes: list[int]) -> None:
        super().__init__(
            "Publication blocked — acknowledgement is required for finding index(es): "
            f"{missing_finding_indexes}."
        )
        self.missing_finding_indexes = missing_finding_indexes


class DuplicateAcknowledgementError(ValidationAppError):
    def __init__(self, finding_index: int) -> None:
        super().__init__(
            f"Finding index {finding_index} was acknowledged more than once — exactly one "
            "acknowledgement is permitted per finding."
        )


class AcknowledgementForNonAcknowledgeableFindingError(ValidationAppError):
    """This sprint's own instructions §10/§17 — an acknowledgement was
    submitted for a finding whose resolved treatment does not require
    (or permit) one (`BLOCK` or `ALLOW_WITHOUT_ACKNOWLEDGEMENT`)."""

    def __init__(self, finding_index: int, resolved_treatment: str) -> None:
        super().__init__(
            f"Finding index {finding_index} resolved to {resolved_treatment}, which does not "
            "require or accept an acknowledgement."
        )


class UnknownAcknowledgementTargetError(ValidationAppError):
    def __init__(self, finding_index: int) -> None:
        super().__init__(
            f"Acknowledgement references finding index {finding_index}, which does not exist "
            "in this publication request."
        )


class MissingAcknowledgementJustificationError(ValidationAppError):
    def __init__(self, finding_index: int) -> None:
        super().__init__(
            f"Acknowledgement for finding index {finding_index} requires a non-empty "
            "justification (findings-and-publication-governance-architecture.md §6 rule 4)."
        )


class DuplicatePublicationEventError(ValidationAppError):
    """This sprint's own chosen concurrency-identity approach — see
    service.py's own module docstring. The same `publication_event_id`
    submitted twice (e.g. a network retry) is rejected rather than
    silently recording a second `PublicationRecord`."""

    def __init__(self, publication_event_id: object) -> None:
        super().__init__(
            f"A Publication Record already exists for publication_event_id "
            f"'{publication_event_id}' — this publish attempt has already been recorded."
        )


class PublicationRecordNotFoundError(NotFoundError):
    def __init__(self, publication_record_id: object) -> None:
        super().__init__(f"Publication Record '{publication_record_id}' not found.")
