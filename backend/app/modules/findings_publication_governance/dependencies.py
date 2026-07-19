"""FastAPI dependencies for Findings and Publication Governance.

Authentication/authorization dependencies (`get_current_user`,
`require_permission`) are IAM's own, reused directly — every module gates
its endpoints the same way.
"""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.modules.findings_publication_governance.service import (
    PublicationRecordService,
    PublicationTreatmentPolicyService,
)


def get_publication_treatment_policy_service(
    db: Session = Depends(get_db),
) -> PublicationTreatmentPolicyService:
    return PublicationTreatmentPolicyService(db)


def get_publication_record_service(db: Session = Depends(get_db)) -> PublicationRecordService:
    return PublicationRecordService(db)
