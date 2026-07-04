"""Substation Registry service layer (CLAUDE.md §14) — business rules,
transactions, orchestration, and audit writing live here, and only here
(CLAUDE.md A1: this module's own tables are written to exclusively by this
layer).

Status transition legality (substation-registry.md §10, revised by ADR-005)
is implemented as a closed allow-list containing exactly the seven edges
ADR-005 defines. ADR-005 replaced Phase 2's original interim allow-list,
which read the architecture document's then-incomplete lifecycle diagram
literally (the diagram omitted `UNDER_CONSTRUCTION` entirely and showed no
direct `ACTIVE -> DECOMMISSIONED` edge) — that gap is now closed; see
ADR-005 for the full decision and rationale.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.modules.substation_registry.exceptions import (
    DuplicateMnemonicError,
    DuplicateNameError,
    DuplicatePsseBusNumberError,
    InvalidGeolocationPairError,
    InvalidStatusTransitionError,
    MnemonicReservedByHistoricalSubstationError,
    NotFoundError,
    ReferenceDataNotFoundError,
)
from app.modules.substation_registry.models import (
    Substation,
    SubstationAlias,
    SubstationAuditLog,
)
from app.modules.substation_registry.repository import SubstationRepository
from app.modules.substation_registry.schemas import (
    SubstationAliasSummary,
    SubstationAuditLogEntry,
    SubstationDetail,
    SubstationSummary,
)
from app.reference_data.repository import ReferenceDataRepository

# Closed allow-list of legal operational_status transitions, keyed by
# reference-data `code` — the seven edges ADR-005 defines. No other
# transition is legal, including PLANNED -> ACTIVE directly (must pass
# through UNDER_CONSTRUCTION).
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "PLANNED": {"UNDER_CONSTRUCTION"},
    "UNDER_CONSTRUCTION": {"ACTIVE"},
    "ACTIVE": {"MOTHBALLED", "DECOMMISSIONED"},
    "MOTHBALLED": {"ACTIVE", "DECOMMISSIONED"},
    "DECOMMISSIONED": {"RETIRED"},
    "RETIRED": set(),
}

# "Create: always starts as Planned or Active (data migration/backfill
# case)" — substation-registry.md §10. A creation-time exception, not a
# transition; unchanged by ADR-005 (confirmed explicitly in that decision).
_ALLOWED_INITIAL_STATUS_CODES = {"PLANNED", "ACTIVE"}


class SubstationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SubstationRepository(db)
        self.reference_data = ReferenceDataRepository(db)
        self.iam = IAMService(db)

    # --- internal helpers -----------------------------------------------------
    def _audit_field_change(
        self,
        *,
        substation_id: uuid.UUID,
        field_name: str,
        old_value: object,
        new_value: object,
        actor_user_id: uuid.UUID,
        change_reason: str | None = None,
    ) -> None:
        """One row per changed field (substation-registry.md §6, §8 rule 8 —
        `field_name` is NOT NULL, unlike IAM's own audit log)."""
        self.repo.add_audit_log(
            SubstationAuditLog(
                substation_id=substation_id,
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

    def _require_reference_data(
        self,
        *,
        region_id: int,
        state_id: int,
        grid_owner_id: int,
    ) -> None:
        if self.reference_data.get_region(region_id) is None:
            raise ReferenceDataNotFoundError("region_id", region_id)
        if self.reference_data.get_state(state_id) is None:
            raise ReferenceDataNotFoundError("state_id", state_id)
        if self.reference_data.get_grid_owner(grid_owner_id) is None:
            raise ReferenceDataNotFoundError("grid_owner_id", grid_owner_id)

    def _require_operational_status(self, operational_status_id: int) -> str:
        """Returns the status's stable `code` (substation-registry.md §6)."""
        status = self.reference_data.get_operational_status(operational_status_id)
        if status is None:
            raise ReferenceDataNotFoundError("operational_status_id", operational_status_id)
        return status.code

    @staticmethod
    def _check_geolocation_pair(latitude: float | None, longitude: float | None) -> None:
        if (latitude is None) != (longitude is None):
            raise InvalidGeolocationPairError()

    def _check_mnemonic_available(
        self, mnemonic: str, *, exclude_substation_id: uuid.UUID | None = None
    ) -> None:
        """Mnemonic uniqueness spans both the live `substation.mnemonic`
        value and every historical `substation_alias.alias_mnemonic` value
        — a mnemonic once assigned is never reassigned to a *different*
        substation (substation-registry.md §8 rule 1). A substation may
        always reuse one of its own historical mnemonics, though: a
        historical alias is "owned" by the substation that originated it,
        not withheld from that same substation (UAT correction — a
        SIDS -> SIDST -> SIDS rename on one substation must succeed).
        `exclude_substation_id` is "the substation this check is on behalf
        of" for both the current-record check and the alias-ownership
        check below.
        """
        existing = self.repo.get_by_mnemonic_ci(mnemonic)
        if existing is not None and existing.substation_id != exclude_substation_id:
            raise DuplicateMnemonicError(mnemonic)

        alias_owner_id = self.repo.find_alias_mnemonic_owner_ci(mnemonic)
        if alias_owner_id is not None and alias_owner_id != exclude_substation_id:
            raise MnemonicReservedByHistoricalSubstationError(mnemonic)

    def _check_name_available(
        self, official_name: str, *, exclude_substation_id: uuid.UUID | None = None
    ) -> None:
        """Unlike mnemonic (`_check_mnemonic_available`), `official_name`
        has no alias-based historical reservation: substation-registry.md
        §8 explicitly treats mnemonic changes as "a special, gated
        operation" (rule 1) while name changes are an ordinary update,
        audit-logged only (§10) — no `SubstationAlias.alias_name` row is
        ever written by `update_substation`. Only current-record
        uniqueness applies here, which already correctly allows a
        substation to rename away from and back to its own former name
        (nothing else currently holds that name once this substation has
        renamed away from it)."""
        existing = self.repo.get_by_name_ci(official_name)
        if existing is not None and existing.substation_id != exclude_substation_id:
            raise DuplicateNameError(official_name)

    def _check_psse_bus_number_available(
        self, psse_bus_number: int, *, exclude_substation_id: uuid.UUID | None = None
    ) -> None:
        existing = self.repo.get_by_psse_bus_number(psse_bus_number)
        if existing is not None and existing.substation_id != exclude_substation_id:
            raise DuplicatePsseBusNumberError(psse_bus_number)

    # --- Create -----------------------------------------------------------------
    def create_substation(
        self,
        *,
        mnemonic: str,
        official_name: str,
        region_id: int,
        state_id: int,
        grid_owner_id: int,
        operational_status_id: int,
        psse_bus_number: int | None,
        latitude: float | None,
        longitude: float | None,
        commissioned_date: date | None,
        remarks: str | None,
        actor_user_id: uuid.UUID,
    ) -> Substation:
        self._check_mnemonic_available(mnemonic)
        self._check_name_available(official_name)
        if psse_bus_number is not None:
            self._check_psse_bus_number_available(psse_bus_number)
        self._check_geolocation_pair(latitude, longitude)
        self._require_reference_data(
            region_id=region_id,
            state_id=state_id,
            grid_owner_id=grid_owner_id,
        )
        status_code = self._require_operational_status(operational_status_id)
        if status_code not in _ALLOWED_INITIAL_STATUS_CODES:
            raise InvalidStatusTransitionError("(new record)", status_code)

        substation = self.repo.add(
            Substation(
                substation_id=uuid.uuid4(),
                mnemonic=mnemonic,
                official_name=official_name,
                region_id=region_id,
                state_id=state_id,
                grid_owner_id=grid_owner_id,
                operational_status_id=operational_status_id,
                psse_bus_number=psse_bus_number,
                latitude=latitude,
                longitude=longitude,
                commissioned_date=commissioned_date,
                remarks=remarks,
                created_by_user_id=actor_user_id,
                updated_by_user_id=actor_user_id,
            )
        )
        # No substation_audit_log row on creation: accountability for the
        # creation event itself is already captured by created_by_user_id/
        # created_at directly on the row (CLAUDE.md §5.4). audit_log's
        # field_name is NOT NULL, which only fits a *changed* field — see
        # module docstring's sibling reasoning for status transitions.
        return substation

    # --- Update (excludes operational_status_id — see change_status) ------------------
    def update_substation(
        self,
        substation_id: uuid.UUID,
        *,
        # mnemonic/official_name/region_id/state_id/grid_owner_id are
        # never-null business fields: `None` unambiguously means "not
        # supplied, leave unchanged." psse_bus_number/latitude/longitude/
        # commissioned_date/remarks are genuinely nullable (clearing them is
        # a valid request), so they default to the `...` (Ellipsis) sentinel
        # instead — "not supplied" and "explicitly set to null" must stay
        # distinguishable for those fields. voltage_level_id is deprecated
        # (ADR-009) and no longer part of this method's update surface —
        # SubstationVoltageYard (ADR-008) is the only way to change a
        # substation's voltage level(s) now.
        mnemonic: str | None = None,
        official_name: str | None = None,
        region_id: int | None = None,
        state_id: int | None = None,
        grid_owner_id: int | None = None,
        psse_bus_number: int | None = ...,
        latitude: float | None = ...,
        longitude: float | None = ...,
        commissioned_date: date | None = ...,
        remarks: str | None = ...,
        actor_user_id: uuid.UUID,
    ) -> Substation:
        substation = self.repo.get_by_id(substation_id)
        if substation is None:
            raise NotFoundError(f"Substation {substation_id} not found")

        changed = False

        if mnemonic is not None and mnemonic != substation.mnemonic:
            self._check_mnemonic_available(mnemonic, exclude_substation_id=substation_id)
            self._retire_mnemonic(substation, actor_user_id=actor_user_id)
            self._audit_field_change(
                substation_id=substation_id,
                field_name="mnemonic",
                old_value=substation.mnemonic,
                new_value=mnemonic,
                actor_user_id=actor_user_id,
            )
            substation.mnemonic = mnemonic
            changed = True

        if official_name is not None and official_name != substation.official_name:
            self._check_name_available(official_name, exclude_substation_id=substation_id)
            self._audit_field_change(
                substation_id=substation_id,
                field_name="official_name",
                old_value=substation.official_name,
                new_value=official_name,
                actor_user_id=actor_user_id,
            )
            substation.official_name = official_name
            changed = True

        if region_id is not None and region_id != substation.region_id:
            if self.reference_data.get_region(region_id) is None:
                raise ReferenceDataNotFoundError("region_id", region_id)
            self._audit_field_change(
                substation_id=substation_id,
                field_name="region_id",
                old_value=substation.region_id,
                new_value=region_id,
                actor_user_id=actor_user_id,
            )
            substation.region_id = region_id
            changed = True

        if state_id is not None and state_id != substation.state_id:
            if self.reference_data.get_state(state_id) is None:
                raise ReferenceDataNotFoundError("state_id", state_id)
            self._audit_field_change(
                substation_id=substation_id,
                field_name="state_id",
                old_value=substation.state_id,
                new_value=state_id,
                actor_user_id=actor_user_id,
            )
            substation.state_id = state_id
            changed = True

        if grid_owner_id is not None and grid_owner_id != substation.grid_owner_id:
            if self.reference_data.get_grid_owner(grid_owner_id) is None:
                raise ReferenceDataNotFoundError("grid_owner_id", grid_owner_id)
            self._audit_field_change(
                substation_id=substation_id,
                field_name="grid_owner_id",
                old_value=substation.grid_owner_id,
                new_value=grid_owner_id,
                actor_user_id=actor_user_id,
            )
            substation.grid_owner_id = grid_owner_id
            changed = True

        if psse_bus_number is not ... and psse_bus_number != substation.psse_bus_number:
            if psse_bus_number is not None:
                self._check_psse_bus_number_available(
                    psse_bus_number, exclude_substation_id=substation_id
                )
            self._audit_field_change(
                substation_id=substation_id,
                field_name="psse_bus_number",
                old_value=substation.psse_bus_number,
                new_value=psse_bus_number,
                actor_user_id=actor_user_id,
            )
            substation.psse_bus_number = psse_bus_number
            changed = True

        if latitude is not ... or longitude is not ...:
            new_latitude = substation.latitude if latitude is ... else latitude
            new_longitude = substation.longitude if longitude is ... else longitude
            if new_latitude != substation.latitude or new_longitude != substation.longitude:
                self._check_geolocation_pair(new_latitude, new_longitude)
                if new_latitude != substation.latitude:
                    self._audit_field_change(
                        substation_id=substation_id,
                        field_name="latitude",
                        old_value=substation.latitude,
                        new_value=new_latitude,
                        actor_user_id=actor_user_id,
                    )
                if new_longitude != substation.longitude:
                    self._audit_field_change(
                        substation_id=substation_id,
                        field_name="longitude",
                        old_value=substation.longitude,
                        new_value=new_longitude,
                        actor_user_id=actor_user_id,
                    )
                substation.latitude = new_latitude
                substation.longitude = new_longitude
                changed = True

        if commissioned_date is not ... and commissioned_date != substation.commissioned_date:
            self._audit_field_change(
                substation_id=substation_id,
                field_name="commissioned_date",
                old_value=substation.commissioned_date,
                new_value=commissioned_date,
                actor_user_id=actor_user_id,
            )
            substation.commissioned_date = commissioned_date
            changed = True

        if remarks is not ... and remarks != substation.remarks:
            self._audit_field_change(
                substation_id=substation_id,
                field_name="remarks",
                old_value=substation.remarks,
                new_value=remarks,
                actor_user_id=actor_user_id,
            )
            substation.remarks = remarks
            changed = True

        if changed:
            substation.updated_by_user_id = actor_user_id
            self.db.flush()

        return substation

    def _retire_mnemonic(self, substation: Substation, *, actor_user_id: uuid.UUID) -> None:
        """Preserve the substation's current mnemonic as a `SubstationAlias`
        before it changes (substation-registry.md §8 rule 1). `valid_from`
        chains from the previous alias's `valid_to` (or the substation's
        `created_at` if this is its first alias), so the full history is
        reconstructible; `valid_to` is the moment of this change.
        """
        latest_alias = self.repo.get_latest_alias(substation.substation_id)
        valid_from = (
            latest_alias.valid_to
            if latest_alias is not None and latest_alias.valid_to is not None
            else substation.created_at
        )
        self.repo.add_alias(
            SubstationAlias(
                substation_id=substation.substation_id,
                alias_mnemonic=substation.mnemonic,
                valid_from=valid_from,
                valid_to=datetime.now(UTC),
            )
        )

    # --- Status change (separate from update_substation — see §10) -----------------
    def change_status(
        self,
        substation_id: uuid.UUID,
        *,
        operational_status_id: int,
        change_reason: str | None,
        actor_user_id: uuid.UUID,
    ) -> Substation:
        substation = self.repo.get_by_id(substation_id)
        if substation is None:
            raise NotFoundError(f"Substation {substation_id} not found")

        current_code = self._require_operational_status(substation.operational_status_id)
        target_code = self._require_operational_status(operational_status_id)

        if operational_status_id == substation.operational_status_id:
            return substation  # idempotent no-op, no audit row

        if target_code not in _STATUS_TRANSITIONS.get(current_code, set()):
            raise InvalidStatusTransitionError(current_code, target_code)

        self._audit_field_change(
            substation_id=substation_id,
            field_name="operational_status_id",
            old_value=current_code,
            new_value=target_code,
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        substation.operational_status_id = operational_status_id
        substation.updated_by_user_id = actor_user_id
        self.db.flush()
        return substation

    # --- Read ---------------------------------------------------------------------
    def get_substation(self, substation_id: uuid.UUID) -> SubstationDetail | None:
        substation = self.repo.get_by_id(substation_id)
        if substation is None:
            return None
        return SubstationDetail(
            substation_id=substation.substation_id,
            mnemonic=substation.mnemonic,
            official_name=substation.official_name,
            region_id=substation.region_id,
            state_id=substation.state_id,
            grid_owner_id=substation.grid_owner_id,
            operational_status_id=substation.operational_status_id,
            psse_bus_number=substation.psse_bus_number,
            latitude=substation.latitude,
            longitude=substation.longitude,
            commissioned_date=substation.commissioned_date,
            remarks=substation.remarks,
            created_at=substation.created_at,
            updated_at=substation.updated_at,
            created_by=self._resolve_user(substation.created_by_user_id),
            updated_by=self._resolve_user(substation.updated_by_user_id),
        )

    def list_substations(
        self,
        *,
        page: int,
        page_size: int,
        region_id: int | None = None,
        state_id: int | None = None,
        grid_owner_id: int | None = None,
        operational_status_id: int | None = None,
        search: str | None = None,
    ) -> tuple[list[SubstationSummary], int]:
        items, total = self.repo.list_substations(
            offset=(page - 1) * page_size,
            limit=page_size,
            region_id=region_id,
            state_id=state_id,
            grid_owner_id=grid_owner_id,
            operational_status_id=operational_status_id,
            search=search,
        )
        return [SubstationSummary.model_validate(s) for s in items], total

    def list_aliases(self, substation_id: uuid.UUID) -> list[SubstationAliasSummary]:
        return [
            SubstationAliasSummary.model_validate(a) for a in self.repo.list_aliases(substation_id)
        ]

    def list_audit_log(
        self, substation_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[SubstationAuditLogEntry], int]:
        items, total = self.repo.list_audit_log(
            substation_id, offset=(page - 1) * page_size, limit=page_size
        )
        entries = [
            SubstationAuditLogEntry(
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
