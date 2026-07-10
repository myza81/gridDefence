"""Automatic Load Shedding Functionality Registry API DTOs (CLAUDE.md A6 —
API DTO layer). Persistence models are never exposed directly (CLAUDE.md
§13) — every response shape here is a distinct Pydantic schema.

Business-rule validation (the target-type/terminal-id XOR, the
"at least one function" rule) is enforced at the service layer, not here —
mirrors Substation Registry's/Equipment Registry's own established
separation between Pydantic request-shape validation and domain business
rules (`app/shared/exceptions.py`'s own docstring).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.schemas import UserSummary
from app.shared.pagination import Page

TargetType = Literal["CIRCUIT_TERMINAL", "TRANSFORMER_TERMINAL"]
# Status Model Refinement (engineering refinement) — the status an engineer
# sees is always exactly one of these three, and is never the same thing as
# the model's own persisted `lifecycle_status` column:
#   AVAILABLE     — functionality exists, not currently referenced by any
#                    active UFLS/UVLS scheme. Computed, never stored.
#   ASSIGNED      — functionality exists, currently referenced by at least
#                    one active UFLS and/or UVLS scheme. Computed, never
#                    stored, and never manually editable.
#   DECOMMISSIONED — functionality permanently removed. The one status
#                    value that *does* correspond 1:1 to a persisted fact.
# See service.py's module docstring for exactly how AVAILABLE/ASSIGNED is
# computed today (current phase: UFLS/UVLS do not exist yet, so this is
# always AVAILABLE for every non-decommissioned record) and how a future
# UFLS/UVLS module supplies real assignment data without this module ever
# querying their tables directly (CLAUDE.md A1).
FunctionalityStatus = Literal["AVAILABLE", "ASSIGNED", "DECOMMISSIONED"]
# EMLS is deliberately never a valid value here — module document §4, §9
# rule 4: this registry has no knowledge of EMLS at all.
SchemeType = Literal["UFLS", "UVLS"]


class FunctionalityCreate(BaseModel):
    """No `status` field — Available is the only possible status for a
    newly created record (Status Model Refinement §1): there is no
    "recorded but not yet confirmed" or "temporarily unavailable" state to
    choose at creation time any more, and Assigned/Decommissioned can never
    be set directly."""

    target_type: TargetType
    circuit_terminal_id: uuid.UUID | None = None
    transformer_terminal_id: uuid.UUID | None = None
    ufls_function: bool = False
    uvls_function: bool = False
    relay_make: str | None = Field(default=None, max_length=100)
    relay_model: str | None = Field(default=None, max_length=100)
    remarks: str | None = None


class FunctionalityUpdate(BaseModel):
    """Partial update of editable metadata only — `target_type`/terminal
    references are immutable after creation (a different target is a
    different record). Status is never edited through this endpoint:
    Available/Assigned are always computed, and Decommissioned has its own
    dedicated, reasoned endpoint below."""

    ufls_function: bool | None = None
    uvls_function: bool | None = None
    relay_make: str | None = Field(default=None, max_length=100)
    relay_model: str | None = Field(default=None, max_length=100)
    remarks: str | None = None
    change_reason: str | None = None


class FunctionalityDecommissionRequest(BaseModel):
    """Used by the decommission endpoint — the only lifecycle transition
    this module still exposes (Status Model Refinement §8). `change_reason`
    is required (enforced at the service layer, module document §10)."""

    change_reason: str | None = None


class FunctionalitySummary(BaseModel):
    """Row shape for the list view."""

    id: uuid.UUID
    target_type: TargetType
    circuit_terminal_id: uuid.UUID | None
    transformer_terminal_id: uuid.UUID | None
    substation_id: uuid.UUID
    substation_mnemonic: str
    voltage_level_label: str
    bay_label: str
    ufls_function: bool
    uvls_function: bool
    status: FunctionalityStatus
    updated_at: datetime


FunctionalityPage = Page[FunctionalitySummary]


class FunctionalityDetail(BaseModel):
    """Full detail view — includes resolved terminal/substation display
    context (read-only, composed from Equipment Registry, never stored
    here — module document §4) and resolved accountability."""

    id: uuid.UUID
    target_type: TargetType
    circuit_terminal_id: uuid.UUID | None
    transformer_terminal_id: uuid.UUID | None
    substation_id: uuid.UUID
    substation_mnemonic: str
    substation_official_name: str
    voltage_level_label: str
    bay_label: str
    ufls_function: bool
    uvls_function: bool
    status: FunctionalityStatus
    relay_make: str | None
    relay_model: str | None
    remarks: str | None
    created_at: datetime
    updated_at: datetime
    created_by: UserSummary | None
    updated_by: UserSummary | None


class FunctionalityAuditLogEntry(BaseModel):
    log_id: int
    field_name: str
    old_value: str | None
    new_value: str | None
    changed_at: datetime
    changed_by: UserSummary | None
    change_reason: str | None


FunctionalityAuditLogPage = Page[FunctionalityAuditLogEntry]


class CandidateTerminal(BaseModel):
    """Section 13 of the module document — one functionally-ready Bay
    Terminal, for scheme-design-time candidate search. Deliberately does
    not know about scheme assignments — see
    `AssignmentAwareCandidateList` below for the composition point that
    will use this once UFLS/UVLS exist."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: TargetType
    circuit_terminal_id: uuid.UUID | None
    transformer_terminal_id: uuid.UUID | None
    substation_id: uuid.UUID
    substation_mnemonic: str
    voltage_level_label: str
    bay_label: str
    ufls_function: bool
    uvls_function: bool


class CandidateTerminalList(BaseModel):
    items: list[CandidateTerminal]
    total: int


class AssignmentAwareCandidateList(BaseModel):
    """Module document §13's `list_assigned_and_available` composition
    result. `assigned_terminal_ids` is supplied by the *caller* (a future
    UFLS/UVLS module, once it exists) — this module never queries another
    module's tables itself (CLAUDE.md A1)."""

    assigned: list[CandidateTerminal]
    available: list[CandidateTerminal]


class CapabilityCheckResponse(BaseModel):
    """Module document §13's `is_ufls_capable`/`is_uvls_capable` — a plain
    yes/no answer, degrading gracefully (`False`) for an unregistered or
    non-existent/decommissioned terminal rather than raising (module
    document §13's "unknown, not invalid" tolerance)."""

    capable: bool
