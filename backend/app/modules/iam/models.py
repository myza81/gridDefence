"""IAM persistence models (CLAUDE.md A6 — Persistence Model layer).

Exact shape per docs/architecture/iam-module.md §11 (Database Design Concept)
and docs/adr/ADR-002-identity-and-access-management.md. Every table here is
owned exclusively by IAM's own service layer (CLAUDE.md A1) — no other
module writes to these tables directly.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserStatus(enum.StrEnum):
    """User.status lifecycle — iam-module.md §8. Soft-delete only (CLAUDE.md §11.6)."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"


class RoleStatus(enum.StrEnum):
    """Role.status lifecycle — iam-module.md §8. Soft-delete only (CLAUDE.md §11.6)."""

    ACTIVE = "active"
    RETIRED = "retired"


class User(Base):
    """The stable, permanent identity record every accountable action resolves
    to (iam-module.md §7.1). Contains no credential material — see
    `UserCredential`.
    """

    __tablename__ = "user"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, native_enum=False, validate_strings=True, length=20),
        nullable=False,
        default=UserStatus.ACTIVE,
    )

    # Self-referential accountability (iam-module.md §6). Nullable only for
    # the bootstrap exception (iam-module.md §9 rule 7) — in practice the
    # bootstrap Administrator self-references its own user_id (see
    # app/modules/iam/bootstrap.py), so this is exercised only as a schema
    # allowance, not a routinely-null column.
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (Index("uq_user_username_ci", func.lower(username), unique=True),)


class UserCredential(Base):
    """Local password credential material — deliberately separated from
    `User` for tighter access control (iam-module.md §7.1, §15). Present
    only for accounts that authenticate locally; never returned in any API
    response shape.
    """

    __tablename__ = "user_credential"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    hash_algorithm: Mapped[str] = mapped_column(String(50), nullable=False)
    last_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Role(Base):
    """A configurable, named collection of permissions (iam-module.md §7.2)."""

    __tablename__ = "role"

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system_role: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[RoleStatus] = mapped_column(
        Enum(RoleStatus, native_enum=False, validate_strings=True, length=20),
        nullable=False,
        default=RoleStatus.ACTIVE,
    )

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    updated_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Permission(Base):
    """One entry in the centrally-registered, code-defined catalog of
    authorizable actions (iam-module.md §7.3). Reference data — registered
    per-module during that module's own deployment/seed process, never
    written at runtime by another module's service layer.
    """

    __tablename__ = "permission"

    permission_id: Mapped[str] = mapped_column(String(150), primary_key=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module_scope: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RolePermission(Base):
    """The grant of one Permission to one Role (iam-module.md §7)."""

    __tablename__ = "role_permission"

    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("role.role_id", ondelete="RESTRICT"), primary_key=True
    )
    permission_id: Mapped[str] = mapped_column(
        String(150), ForeignKey("permission.permission_id", ondelete="RESTRICT"), primary_key=True
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )


class UserRole(Base):
    """The grant of one Role to one User, with a validity window
    (iam-module.md §7.4). Never deleted — a revoked grant sets `revoked_at`.
    """

    __tablename__ = "user_role"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("role.role_id", ondelete="RESTRICT"), nullable=False
    )
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        # At most one currently-active (revoked_at IS NULL) grant of the same
        # role to the same user — prevents duplicate concurrent grants
        # (iam-module.md §10). Portable partial unique index: enforced on
        # both PostgreSQL (production) and SQLite (this environment's test
        # stand-in, see backend/conftest.py).
        Index(
            "uq_user_role_active",
            "user_id",
            "role_id",
            unique=True,
            postgresql_where=text("revoked_at IS NULL"),
            sqlite_where=text("revoked_at IS NULL"),
        ),
    )


class ExternalIdentityMapping(Base):
    """The mapping between a User and an external authentication principal,
    with a validity window (iam-module.md §7.5). Zero, one, or several
    concurrent mappings per user are permitted.
    """

    __tablename__ = "external_identity_mapping"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    external_principal_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    linked_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )

    __table_args__ = (
        # (external_principal_id, provider) unique among currently-linked
        # mappings only (iam-module.md §10) — no two Users may simultaneously
        # claim the same external identity.
        Index(
            "uq_external_identity_active",
            "external_principal_id",
            "provider",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
            sqlite_where=text("unlinked_at IS NULL"),
        ),
    )


class IAMAuditLog(Base):
    """IAM's own audit trail (CLAUDE.md A4), covering every entity above.

    `changed_by_user_id` is nullable only for the bootstrap exception
    (iam-module.md §9 rule 7) — see app/modules/iam/bootstrap.py, which in
    practice always supplies a real (self-referential) user_id rather than
    exercising this nullability.
    """

    __tablename__ = "iam_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(150), nullable=False)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
