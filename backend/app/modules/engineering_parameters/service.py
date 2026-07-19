"""Engineering Parameter Configuration service layer (CLAUDE.md §14) —
business rules, transactions, orchestration, and audit writing live here,
and only here (CLAUDE.md A1: this module's own tables are written to
exclusively by this layer).

Lifecycle (ADR-021, module document §8): current-value-plus-audit-log, not
a Draft/Published state machine. `set_parameter_value` is a single-method
upsert — it creates the parameter on first use, or updates its current
value thereafter, and is the *only* write path this module exposes.
Every call is audited (old value, new value, actor, mandatory reason,
timestamp), including the very first value a parameter is ever given.

`unit`/`description` are secondary, non-engineering-significant metadata
(module document §5, §11's own conceptual schema): when omitted (`None`)
on a call that updates an already-existing parameter, the existing value
is preserved rather than cleared, so a caller changing only `value` never
accidentally wipes out a parameter's recorded unit/description. Only
`value` changes are recorded in the audit trail (module document §14 —
"old value, new value" is deliberately singular: a tolerance value has
exactly one audited fact, not several independently-tracked fields the
way a richer entity like `AutomaticLoadSheddingFunctionality` has).

Per-`parameter_key` value validation (module document §10) lives in
`_NUMERIC_PARAMETER_BOUNDS`, below — a small, explicit, code-level
registry. Adding a future numeric parameter's validation is a new dict
entry, never a schema change (module document §17); a parameter with no
registered bounds is accepted as any non-empty string, deferring stricter
validation to whenever that parameter is actually introduced (CLAUDE.md
§21 — no validation invented ahead of a documented need).
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.modules.engineering_parameters.exceptions import (
    ChangeReasonRequiredError,
    InvalidParameterValueError,
    ParameterNotFoundError,
)
from app.modules.engineering_parameters.models import (
    EngineeringParameter,
    EngineeringParameterAuditLog,
)
from app.modules.engineering_parameters.repository import EngineeringParameterRepository
from app.modules.engineering_parameters.schemas import (
    EngineeringParameterAuditLogEntry,
    EngineeringParameterDetail,
)
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService

# Module document §10: percentage-shaped parameters must be a valid number,
# greater than 0 and at most 100 — a mathematical fact about what a
# percentage tolerance means, not an invented engineering policy. Only
# `mw_tolerance_percentage` is architecture-approved today
# (continuous-evaluation-architecture.md §7); a future parameter adds its
# own entry here when it is introduced, not before.
_NUMERIC_PARAMETER_BOUNDS: dict[str, tuple[float, float]] = {
    "mw_tolerance_percentage": (0.0, 100.0),
}


class EngineeringParameterService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = EngineeringParameterRepository(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _audit(
        self,
        *,
        parameter_key: str,
        old_value: str | None,
        new_value: str | None,
        actor_user_id: uuid.UUID | None,
        change_reason: str | None,
    ) -> None:
        self.repo.add_audit_log(
            EngineeringParameterAuditLog(
                parameter_key=parameter_key,
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

    def _validate_value(self, parameter_key: str, value: str) -> None:
        if not value or not value.strip():
            raise InvalidParameterValueError(parameter_key, "value must not be empty.")
        bounds = _NUMERIC_PARAMETER_BOUNDS.get(parameter_key)
        if bounds is None:
            return
        low, high = bounds
        try:
            numeric_value = float(value)
        except ValueError as exc:
            raise InvalidParameterValueError(
                parameter_key, f"must be a valid number, got '{value}'."
            ) from exc
        if not (low < numeric_value <= high):
            raise InvalidParameterValueError(
                parameter_key,
                f"must be greater than {low} and at most {high}, got {numeric_value}.",
            )

    def _to_detail(self, parameter: EngineeringParameter) -> EngineeringParameterDetail:
        return EngineeringParameterDetail(
            parameter_key=parameter.parameter_key,
            value=parameter.value,
            unit=parameter.unit,
            description=parameter.description,
            updated_at=parameter.updated_at,
            updated_by=self._resolve_user(parameter.updated_by_user_id),
        )

    # --- Write (the only write path this module exposes) ----------------------
    def set_parameter_value(
        self,
        parameter_key: str,
        *,
        value: str,
        unit: str | None,
        description: str | None,
        change_reason: str,
        actor_user_id: uuid.UUID | None,
    ) -> EngineeringParameter:
        """Upsert (module document §8): creates the parameter on first
        use, or updates its current value thereafter. Always audited,
        always requires a non-empty `change_reason` — even the very
        first value a parameter is ever given (module document §9
        rule 1)."""
        if not change_reason or not change_reason.strip():
            raise ChangeReasonRequiredError()
        self._validate_value(parameter_key, value)

        existing = self.repo.get_by_key(parameter_key)
        if existing is None:
            parameter = self.repo.add(
                EngineeringParameter(
                    parameter_key=parameter_key,
                    value=value,
                    unit=unit,
                    description=description,
                    updated_by_user_id=actor_user_id,
                )
            )
            self._audit(
                parameter_key=parameter_key,
                old_value=None,
                new_value=value,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            self.db.flush()
            return parameter

        if value != existing.value:
            self._audit(
                parameter_key=parameter_key,
                old_value=existing.value,
                new_value=value,
                actor_user_id=actor_user_id,
                change_reason=change_reason,
            )
            existing.value = value
        if unit is not None:
            existing.unit = unit
        if description is not None:
            existing.description = description
        existing.updated_by_user_id = actor_user_id
        self.db.flush()
        return existing

    # --- Read -------------------------------------------------------------------
    def get_parameter(self, parameter_key: str) -> EngineeringParameterDetail | None:
        parameter = self.repo.get_by_key(parameter_key)
        return self._to_detail(parameter) if parameter else None

    def list_parameters(self) -> list[EngineeringParameterDetail]:
        return [self._to_detail(p) for p in self.repo.list_all()]

    def list_audit_log(
        self, parameter_key: str, *, page: int, page_size: int
    ) -> tuple[list[EngineeringParameterAuditLogEntry], int]:
        if self.repo.get_by_key(parameter_key) is None:
            raise ParameterNotFoundError(parameter_key)
        items, total = self.repo.list_audit_log(
            parameter_key, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            EngineeringParameterAuditLogEntry(
                log_id=e.log_id,
                parameter_key=e.parameter_key,
                old_value=e.old_value,
                new_value=e.new_value,
                changed_at=e.changed_at,
                changed_by=self._resolve_user(e.changed_by_user_id),
                change_reason=e.change_reason,
            )
            for e in items
        ]
        return entries, total

    # --- Service interface for future modules (ADR-021 §13; ADR-022's own
    # MW tolerance detector is the first anticipated caller) ---------------------
    def get_parameter_value(self, parameter_key: str) -> str | None:
        """Read-only, in-process interface for any module needing an
        engineering parameter's current value (CLAUDE.md A1) — returns
        `None` if the parameter does not exist rather than raising, since
        a consuming detector has no engineering-meaningful action to take
        beyond reporting its own inability to evaluate."""
        parameter = self.repo.get_by_key(parameter_key)
        return parameter.value if parameter else None
