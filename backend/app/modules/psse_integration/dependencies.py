"""FastAPI dependencies for PSS/E Integration.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly (app/modules/iam/
dependencies.py) — every module gates its write endpoints the same way.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.psse_integration.service import PsseIntegrationService


def get_psse_integration_service(db: Session = Depends(get_db)) -> PsseIntegrationService:
    return PsseIntegrationService(db)
