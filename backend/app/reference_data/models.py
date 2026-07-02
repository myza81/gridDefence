"""Core Platform reference/lookup tables.

Exact shape per docs/architecture/substation-registry.md §6:
voltage_level, region, state, grid_owner, operational_status. These are
reference data (CLAUDE.md §11.3) — small-integer surrogate keys, not UUIDs
(CLAUDE.md A5) — used as read-only lookups by every module that needs them.
Phase 1 owns their existence and seed content; no business module owns them.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# PostgreSQL (production) gets exactly the SMALLINT primary key
# substation-registry.md §6 specifies. SQLite (this environment's test
# stand-in — no Docker/local PostgreSQL available, see Phase 1's final
# report) only grants its rowid-autoincrement behaviour to a column
# literally typed INTEGER PRIMARY KEY, not SMALLINT — so other dialects fall
# back to plain INTEGER via this variant. Behaviourally identical either way;
# only the on-disk column type differs.
_ReferenceKey = Integer().with_variant(SmallInteger(), "postgresql")


class VoltageLevel(Base):
    __tablename__ = "voltage_level"

    voltage_level_id: Mapped[int] = mapped_column(
        _ReferenceKey, primary_key=True, autoincrement=True
    )
    label: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    nominal_kv: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class Region(Base):
    __tablename__ = "region"

    region_id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)


class State(Base):
    __tablename__ = "state"

    state_id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)


class GridOwner(Base):
    __tablename__ = "grid_owner"

    grid_owner_id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)


class OperationalStatus(Base):
    __tablename__ = "operational_status"

    operational_status_id: Mapped[int] = mapped_column(
        _ReferenceKey, primary_key=True, autoincrement=True
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    is_terminal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
