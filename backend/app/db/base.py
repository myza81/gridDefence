"""Shared SQLAlchemy declarative base.

Every module's persistence models (CLAUDE.md A6 — Persistence Model layer)
inherit from `Base` so that Alembic's autogenerate can discover them via a
single shared metadata object.

Phase 0 intentionally defines no domain tables here. Future module phases
import `Base` in their own `models.py` (e.g. `app/modules/iam/models.py`)
and Alembic's `env.py` imports each module's models so they register with
`Base.metadata` before autogenerate runs.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base shared by every module's persistence models."""
