"""The shared Defence Scheme Version persistence mixin (CLAUDE.md A6 —
Persistence Model layer; shared-defence-scheme-domain-model.md §2, §4).

**`SchemeVersionMixin` is not a table.** `scheme-future-extensibility.md`
is explicit: "This pack deliberately does not build a single, generic
'Assignment' or 'Scheme' abstraction that UFLS/UVLS/EMLS/future schemes
all inherit from identically" — there is no shared, generic
`scheme_version` table with a `scheme_type` discriminator column.
Instead, each concrete future scheme module (UFLS, UVLS, EMLS, and
beyond) declares its **own** concrete table (e.g. `ufls_scheme_version`)
that inherits from this mixin to pick up the columns genuinely common to
every scheme's version lifecycle, and adds its own scheme-specific
columns (stage structure references, priority-group ownership, etc.)
alongside them. `__abstract__ = True` — SQLAlchemy never registers this
class itself as a table; nothing is created by this module's own
(nonexistent) migration.

Deliberately **excluded** from this mixin, and left to each concrete
module to add itself: `scheme_id`, `superseded_by_version_id`. Both are
foreign keys whose *target* genuinely differs per concrete module (each
module owns its own Defence Scheme identity table) or are self-referential
in a way `declared_attr` machinery would add real complexity for a single
column's benefit — not worth abstracting away, per CLAUDE.md §21. Every
other shared field below is fully mixin-provided.

Every column here maps directly to ADR-015's own four-state lifecycle —
no `review_status`/`approval_status`/`archived_at` fields exist, since
those states do not exist under the ratified model.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus


class SchemeVersionMixin:
    """Shared columns for one Defence Scheme Version aggregate root
    (shared-defence-scheme-domain-model.md §2). A concrete module's own
    model adds `scheme_id` (its own FK), its own scheme-specific columns,
    and any `__tablename__`/`__table_args__` it needs — see
    `scheme_version_lifecycle_check_sql()` below for the one shared
    constraint every concrete table should include in its own
    `__table_args__`.
    """

    __abstract__ = True

    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Sequential, per-scheme (this sprint's own chosen scheme: 1, 2, 3...
    # scoped to `scheme_id` — computed by `repository.get_next_version_
    # number`, never engineer-entered). Not itself a lifecycle concept,
    # but common metadata every scheme version needs, per this sprint's
    # own instructions §1.
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    lifecycle_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SchemeVersionLifecycleStatus.DRAFT.value
    )

    # --- Publish (Draft -> Published) -------------------------------------------
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Supersede (Published -> Superseded, automatic) -------------------------
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Entered in Error (Published|Superseded -> Entered in Error) ------------
    entered_in_error_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    entered_in_error_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    engineering_remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # --- Actor attribution (real FKs into IAM's own `user` table; IAM
    # already exists for every concrete module, unlike a scheme-specific
    # identity table, so these are plain columns, not `declared_attr`) ------------
    published_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    entered_in_error_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )


def scheme_version_lifecycle_check_sql(column_name: str = "lifecycle_status") -> str:
    """The one shared `CHECK` constraint expression every concrete
    module's own `__table_args__` should include (CLAUDE.md §11.8) —
    returned as a plain SQL fragment, not a `declared_attr`-based
    `__table_args__` override, so a concrete module can combine it with
    its own constraints explicitly and legibly rather than relying on
    declarative-inheritance merge behaviour."""
    values = ",".join(f"'{status.value}'" for status in SchemeVersionLifecycleStatus)
    return f"{column_name} IN ({values})"
