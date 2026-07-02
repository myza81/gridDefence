"""IAM router (CLAUDE.md §14) — HTTP, request validation, authentication only.

No business logic lives here — every handler delegates to `IAMService`.
Resource shape follows docs/architecture/iam-module.md §12: `users`,
`users/me`, `users/{id}/roles`, `roles`, `roles/{id}/permissions`,
`permissions`, plus the authentication-adjacent `auth/login` endpoint
(§12: "their exact shape is an implementation detail... this contract only
specifies that such endpoints resolve to a user_id").
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.modules.iam.dependencies import get_current_user, get_iam_service, require_permission
from app.modules.iam.exceptions import AppError, NotFoundError, ValidationAppError
from app.modules.iam.models import User
from app.modules.iam.schemas import (
    GrantPermissionRequest,
    GrantRoleRequest,
    LoginRequest,
    LoginResponse,
    PermissionCreate,
    PermissionSummary,
    RoleCreate,
    RoleSummary,
    UserCreate,
    UserPage,
    UserRoleSummary,
    UserSummary,
)
from app.modules.iam.security import issue_access_token
from app.modules.iam.service import IAMService

router = APIRouter(tags=["iam"])


def _error_response(exc: AppError) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code, detail={"code": exc.code, "message": exc.message})


# --- Authentication (local username/password only — Phase 1 scope) --------------
@router.post("/auth/login", response_model=LoginResponse)
def login(payload: LoginRequest, service: IAMService = Depends(get_iam_service)) -> LoginResponse:
    try:
        user = service.authenticate(payload.username, payload.password)
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    token = issue_access_token(user.user_id)
    return LoginResponse(access_token=token, user=UserSummary.model_validate(user))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(_current_user: User = Depends(get_current_user)) -> None:
    """Informational only: access tokens are stateless (security.py) — there
    is no server-side session to invalidate in Phase 1. The client discards
    the token. A revocation list is a Future Extension, not implemented here.
    """
    return None


# --- Users -----------------------------------------------------------------------
@router.get("/users/me", response_model=UserSummary)
def get_current_user_summary(current_user: User = Depends(get_current_user)) -> UserSummary:
    return UserSummary.model_validate(current_user)


@router.get("/users", response_model=UserPage)
def list_users(
    page: int = 1,
    page_size: int = 50,
    service: IAMService = Depends(get_iam_service),
    _actor: User = Depends(require_permission("iam.user.manage")),
) -> UserPage:
    items, total = service.list_users(page=page, page_size=page_size)
    return UserPage(items=items, page=page, page_size=page_size, total=total)


@router.post("/users", response_model=UserSummary, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.user.manage")),
) -> UserSummary:
    try:
        user = service.create_user(
            username=payload.username,
            display_name=payload.display_name,
            email=payload.email,
            password=payload.password,
            actor_user_id=actor.user_id,
        )
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return UserSummary.model_validate(user)


@router.get("/users/{user_id}/roles", response_model=list[UserRoleSummary])
def list_user_roles(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: IAMService = Depends(get_iam_service),
) -> list[UserRoleSummary]:
    # A user may always view their own roles; viewing another user's roles
    # requires iam.user.manage.
    if user_id != current_user.user_id and not service.has_permission(
        current_user.user_id, "iam.user.manage"
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, detail="Missing required permission: iam.user.manage"
        )
    return service.list_user_roles(user_id)


@router.post(
    "/users/{user_id}/roles", response_model=UserRoleSummary, status_code=status.HTTP_201_CREATED
)
def grant_user_role(
    user_id: uuid.UUID,
    payload: GrantRoleRequest,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.user.manage")),
) -> UserRoleSummary:
    try:
        service.assign_role_to_user(
            user_id=user_id, role_id=payload.role_id, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    matches = [r for r in service.list_user_roles(user_id) if r.role.role_id == payload.role_id]
    return matches[0]


@router.delete("/users/{user_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_user_role(
    user_id: uuid.UUID,
    role_id: uuid.UUID,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.user.manage")),
) -> None:
    try:
        service.revoke_role_from_user(user_id=user_id, role_id=role_id, actor_user_id=actor.user_id)
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return None


# --- Roles -------------------------------------------------------------------------
@router.get("/roles", response_model=list[RoleSummary])
def list_roles(
    service: IAMService = Depends(get_iam_service),
    _current_user: User = Depends(get_current_user),
) -> list[RoleSummary]:
    return service.list_roles()


@router.post("/roles", response_model=RoleSummary, status_code=status.HTTP_201_CREATED)
def create_role(
    payload: RoleCreate,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.role.manage")),
) -> RoleSummary:
    try:
        role = service.create_role(
            name=payload.name, description=payload.description, actor_user_id=actor.user_id
        )
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return RoleSummary.model_validate(role)


@router.get("/roles/{role_id}/permissions", response_model=list[PermissionSummary])
def list_role_permissions(
    role_id: uuid.UUID,
    service: IAMService = Depends(get_iam_service),
    _current_user: User = Depends(get_current_user),
) -> list[PermissionSummary]:
    return service.list_role_permissions(role_id)


@router.post(
    "/roles/{role_id}/permissions",
    response_model=list[PermissionSummary],
    status_code=status.HTTP_201_CREATED,
)
def grant_role_permission(
    role_id: uuid.UUID,
    payload: GrantPermissionRequest,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.role.manage")),
) -> list[PermissionSummary]:
    try:
        service.grant_permission_to_role(
            role_id=role_id, permission_id=payload.permission_id, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return service.list_role_permissions(role_id)


@router.delete(
    "/roles/{role_id}/permissions/{permission_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_role_permission(
    role_id: uuid.UUID,
    permission_id: str,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.role.manage")),
) -> None:
    try:
        service.revoke_permission_from_role(
            role_id=role_id, permission_id=permission_id, actor_user_id=actor.user_id
        )
    except AppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return None


# --- Permissions (read-only catalog) ------------------------------------------------
@router.get("/permissions", response_model=list[PermissionSummary])
def list_permissions(
    service: IAMService = Depends(get_iam_service),
    _current_user: User = Depends(get_current_user),
) -> list[PermissionSummary]:
    return service.list_permissions()


@router.post("/permissions", response_model=PermissionSummary, status_code=status.HTTP_201_CREATED)
def register_permission(
    payload: PermissionCreate,
    service: IAMService = Depends(get_iam_service),
    actor: User = Depends(require_permission("iam.role.manage")),
) -> PermissionSummary:
    """Administrative registration of a new catalog entry. In normal
    operation, permissions are registered per-module during that module's own
    seed process (iam-module.md §7.3) — this endpoint exists for
    administrative/manual catalog management, not as the primary
    registration path.
    """
    try:
        permission = service.register_permission_strict(
            permission_id=payload.permission_id,
            label=payload.label,
            description=payload.description,
            module_scope=payload.module_scope,
        )
    except ValidationAppError as exc:
        raise _error_response(exc) from exc

    service.db.commit()
    return PermissionSummary.model_validate(permission)
