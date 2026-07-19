"""A test-only concrete model built from `SchemeVersionMixin` — proves
the mixin is genuinely reusable without any real scheme module existing
(this sprint's own instructions: "build the reusable infrastructure...
Do not begin UFLS/UVLS/EMLS"). Never a production table, never part of
any Alembic migration, never exposed through any router — imported only
by this module's own tests, mirroring the established
`continuous_evaluation.tests.synthetic_evaluation` precedent.

`scheme_id` is a bare UUID column, no foreign key: a real concrete
module would reference its own Defence Scheme identity table (excluded
from the shared mixin deliberately — see `models.py`'s own docstring);
no such table exists for this synthetic test double, and inventing one
would test referential integrity the mixin itself does not own.
"""

from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.modules.scheme_platform.models import (
    SchemeVersionMixin,
    scheme_version_lifecycle_check_sql,
)


class SyntheticSchemeVersion(SchemeVersionMixin, Base):
    __tablename__ = "test_synthetic_scheme_version"

    scheme_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)

    __table_args__ = (
        CheckConstraint(
            scheme_version_lifecycle_check_sql(), name="ck_test_synthetic_scheme_version_status"
        ),
    )
