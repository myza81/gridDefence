"""Shared Defence Scheme Version repository helpers (CLAUDE.md §14 —
pure persistence, no business rules). Plain functions parameterized by
the concrete SQLAlchemy model class a future scheme module supplies —
not a generic base-repository class hierarchy (CLAUDE.md §21: this is
the minimum machinery four reusable queries actually need). Each
concrete module still owns and calls these against its own table; this
module never holds a database session of its own and never queries
across modules.
"""

from __future__ import annotations

import uuid
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.scheme_platform.lifecycle import SchemeVersionLifecycleStatus
from app.modules.scheme_platform.models import SchemeVersionMixin

ModelT = TypeVar("ModelT", bound=SchemeVersionMixin)


def get_next_version_number(db: Session, model_class: type[ModelT], scheme_id: uuid.UUID) -> int:
    """The next sequential `version_number` for `scheme_id` — `1` if no
    version yet exists for that scheme."""
    current_max = db.execute(
        select(func.max(model_class.version_number)).where(model_class.scheme_id == scheme_id)
    ).scalar_one()
    return (current_max or 0) + 1


def get_current_published(
    db: Session, model_class: type[ModelT], scheme_id: uuid.UUID
) -> ModelT | None:
    """At most one row can ever match — ADR-015: "Only one Published
    version may exist per scheme at a time.\""""
    stmt = select(model_class).where(
        model_class.scheme_id == scheme_id,
        model_class.lifecycle_status == SchemeVersionLifecycleStatus.PUBLISHED,
    )
    return db.execute(stmt).scalar_one_or_none()


def list_versions(db: Session, model_class: type[ModelT], scheme_id: uuid.UUID) -> list[ModelT]:
    """All versions for one scheme, newest `version_number` first."""
    stmt = (
        select(model_class)
        .where(model_class.scheme_id == scheme_id)
        .order_by(model_class.version_number.desc())
    )
    return list(db.execute(stmt).scalars().all())
