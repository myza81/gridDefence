"""FastAPI dependencies for the Sensitive Customer Registry.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly — every module gates
its endpoints the same way.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.sensitive_customer_registry.service import SensitiveCustomerRegistryService


def get_sensitive_customer_registry_service(
    db: Session = Depends(get_db),
) -> SensitiveCustomerRegistryService:
    return SensitiveCustomerRegistryService(db)
