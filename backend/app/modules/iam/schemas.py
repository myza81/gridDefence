"""IAM API DTOs (CLAUDE.md A6 — API DTO layer).

`UserCredential` has no schema here and must never appear in any response
shape (iam-module.md §12, §15) — enforced by simply never referencing it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.iam.models import RoleStatus, UserStatus


# --- Users -------------------------------------------------------------------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=150)
    display_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class UserSummary(BaseModel):
    """Read-only lookup shape — iam-module.md §13 `getUser()`."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    username: str
    display_name: str
    email: str | None
    status: UserStatus


class UserDetail(UserSummary):
    created_at: datetime
    updated_at: datetime


class UserPage(BaseModel):
    items: list[UserSummary]
    page: int
    page_size: int
    total: int


class UserStatusChange(BaseModel):
    """IAM Completion Sprint — a status transition always carries a
    mandatory, non-empty reason (`min_length=1` catches an outright empty
    string at the request-shape layer; the service layer additionally
    rejects a whitespace-only reason, since `min_length` alone cannot)."""

    status: UserStatus
    change_reason: str = Field(min_length=1, max_length=500)


# --- Roles ---------------------------------------------------------------------
class RoleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role_id: uuid.UUID
    name: str
    description: str | None
    is_system_role: bool
    status: RoleStatus


# --- Permissions -----------------------------------------------------------------
class PermissionCreate(BaseModel):
    permission_id: str = Field(min_length=1, max_length=150)
    label: str = Field(min_length=1, max_length=200)
    description: str | None = None
    module_scope: str = Field(min_length=1, max_length=100)


class PermissionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permission_id: str
    label: str
    description: str | None
    module_scope: str


# --- Grants -----------------------------------------------------------------------
class GrantRoleRequest(BaseModel):
    role_id: uuid.UUID


class GrantPermissionRequest(BaseModel):
    permission_id: str


class UserRoleSummary(BaseModel):
    """iam-module.md §13 `listUserRoles()` — roles/permissions summary."""

    role: RoleSummary
    granted_at: datetime
    permissions: list[str]


# --- Authentication (local username/password only — iam-module.md §4) -----------
class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserSummary
