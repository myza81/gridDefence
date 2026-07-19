"""FastAPI dependencies for Engineering Parameter Configuration.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly — every module gates
its endpoints the same way.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.engineering_parameters.service import EngineeringParameterService


def get_engineering_parameter_service(
    db: Session = Depends(get_db),
) -> EngineeringParameterService:
    return EngineeringParameterService(db)
