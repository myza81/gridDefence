"""Shared Defence Scheme Version API DTOs (CLAUDE.md A6 — API DTO layer).

These are reusable **base** shapes a concrete future scheme module's own
schemas extend (Pydantic model inheritance) rather than duplicate —
never persistence models exposed directly (CLAUDE.md §13). A concrete
module's own `SchemeVersionDetail` adds its own scheme-specific fields
(stage structure, priority groups, assignments) on top of these.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.modules.iam.schemas import UserSummary
from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus


class SchemeVersionLifecycleInfo(BaseModel):
    """The shared lifecycle/metadata fields every concrete scheme
    version's own summary/detail DTO includes verbatim (by composition —
    a concrete DTO adds `lifecycle: SchemeVersionLifecycleInfo` as one
    field, or inherits `SchemeVersionSummaryBase`/`SchemeVersionDetailBase`
    directly, whichever reads better for that module)."""

    version_id: uuid.UUID
    scheme_id: uuid.UUID
    version_number: int
    lifecycle_status: SchemeVersionLifecycleStatus

    published_at: datetime | None
    published_by: UserSummary | None

    superseded_at: datetime | None

    entered_in_error_at: datetime | None
    entered_in_error_by: UserSummary | None
    entered_in_error_reason: str | None

    engineering_remarks: str | None

    created_at: datetime
    updated_at: datetime


class SchemeVersionSummaryBase(BaseModel):
    """Minimal, list-view shape — a concrete module's own summary DTO
    extends this with its own scheme-type-specific display fields."""

    version_id: uuid.UUID
    scheme_id: uuid.UUID
    version_number: int
    lifecycle_status: SchemeVersionLifecycleStatus
    published_at: datetime | None
    engineering_remarks: str | None


class SchemeVersionDetailBase(SchemeVersionSummaryBase):
    """Full detail-view shape — a concrete module's own detail DTO
    extends this with its own owned structure (stages/priority groups,
    assignments)."""

    published_by: UserSummary | None
    superseded_at: datetime | None
    entered_in_error_at: datetime | None
    entered_in_error_by: UserSummary | None
    entered_in_error_reason: str | None
    created_at: datetime
    updated_at: datetime


class EnterInErrorRequest(BaseModel):
    """Shared request body shape for the one lifecycle action that takes
    caller-supplied input beyond identity — ADR-015's own mandatory
    reason for an administrative correction."""

    reason: str
