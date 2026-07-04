"""FastAPI dependencies for Equipment Registry.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly (app/modules/iam/
dependencies.py) — every module gates its write endpoints the same way.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.equipment_registry.service import EquipmentRegistryService


def get_equipment_registry_service(db: Session = Depends(get_db)) -> EquipmentRegistryService:
    return EquipmentRegistryService(db)
