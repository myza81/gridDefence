"""FastAPI dependencies for the Automatic Load Shedding Functionality
Registry.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly — every module gates
its write endpoints the same way.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.automatic_load_shedding_functionality.service import (
    AutomaticLoadSheddingFunctionalityService,
)


def get_automatic_load_shedding_functionality_service(
    db: Session = Depends(get_db),
) -> AutomaticLoadSheddingFunctionalityService:
    return AutomaticLoadSheddingFunctionalityService(db)
