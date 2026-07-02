"""FastAPI dependencies for authentication and authorization.

Every other module's router will eventually import `require_permission` the
same way this module's own router does — the single, shared way any endpoint
in GridDefence gates access, per iam-module.md §13 (`hasPermission` is "the
single authorization decision point every other module's service layer
calls").
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.iam.models import User, UserStatus
from app.modules.iam.security import InvalidTokenError, verify_access_token
from app.modules.iam.service import IAMService

_bearer_scheme = HTTPBearer(auto_error=False)


def get_iam_service(db: Session = Depends(get_db)) -> IAMService:
    return IAMService(db)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    service: IAMService = Depends(get_iam_service),
) -> User:
    """Resolve the bearer token to an active `User`.

    Raises 401 for any failure mode (missing token, invalid/expired token,
    unknown user, inactive user) — never falls back to an implicit identity
    (CLAUDE.md A10: authentication is required for all non-public endpoints).
    """
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        user_id: uuid.UUID = verify_access_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user = service.repo.get_user_by_id(user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return user


def require_permission(permission_code: str) -> Callable[..., User]:
    """Dependency factory: `Depends(require_permission("iam.role.manage"))`.

    Calls `hasPermission` (iam-module.md §13) — fails closed, per §9 rule 11,
    on any unrecognized or unregistered permission code.
    """

    def _dependency(
        current_user: User = Depends(get_current_user),
        service: IAMService = Depends(get_iam_service),
    ) -> User:
        if not service.has_permission(current_user.user_id, permission_code):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission_code}",
            )
        return current_user

    return _dependency
