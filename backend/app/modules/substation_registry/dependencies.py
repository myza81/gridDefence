"""FastAPI dependencies for Substation Registry.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly rather than
reimplemented — every module gates its write endpoints the same way
(app/modules/iam/dependencies.py).
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.substation_registry.service import SubstationService


def get_substation_service(db: Session = Depends(get_db)) -> SubstationService:
    return SubstationService(db)
