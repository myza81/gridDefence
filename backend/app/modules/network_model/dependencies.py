"""FastAPI dependencies for Network Model.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly — mirrors every other
module's own dependencies.py.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.network_model.service import NetworkModelService


def get_network_model_service(db: Session = Depends(get_db)) -> NetworkModelService:
    return NetworkModelService(db)
