"""Core Platform reference/lookup tables.

Exact shape per docs/architecture/substation-registry.md §6:
voltage_level, region, state, grid_owner, operational_status. These are
reference data (CLAUDE.md §11.3) — small-integer surrogate keys, not UUIDs
(CLAUDE.md A5) — used as read-only lookups by every module that needs them.
Phase 1 owns their existence and seed content; no business module owns them.
"""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
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


class LineType(Base):
    """A circuit's physical construction type (overhead/cable/submarine/
    hybrid). Added by Phase 3 (Equipment Registry) per
    docs/architecture/equipment-registry-module.md §6, §7.4: owned by Core
    Platform, following the exact `voltage_level`/`region`/`grid_owner`
    pattern (CLAUDE.md §11.3), even though the concept it describes belongs
    to Equipment Registry's own domain.
    """

    __tablename__ = "line_type"

    line_type_id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(50), nullable=False)


class TransformerBreakerNumberingConvention(Base):
    """The TNB transformer breaker-number *suggestion* convention
    (equipment-registry-module.md Transformer Registry Business Rule 7),
    keyed by (HV voltage level, LV voltage level, side). Previously
    hardcoded in `frontend/src/modules/equipment_registry/
    transformerBreakerSuggestion.ts` as a TypeScript table — moved here so
    the convention is auditable, seedable, and maintainable (e.g. a new
    transformation pair, or a corrected pattern) without a frontend code
    change, per CLAUDE.md §11.3 (reference tables preferred over hardcoded
    application constants).

    This is display-only suggestion data, not a validation rule: `pattern`
    may be `NULL` (no suggestion exists for this side, e.g. the 500kV side
    of a 500/275kV transformer — non-standard, per the convention) and the
    backend never validates a `TransformerTerminal.breaker_number` against
    it. `is_standard = false` marks a side that is deliberately left
    without an automatic suggestion (distinct from a side simply not yet
    documented) — a row with `is_standard = false` should have
    `pattern IS NULL`, though this is a data-authoring convention, not a
    database-enforced invariant (no known reason for a future exception,
    but not worth a `CHECK` constraint either — CLAUDE.md §21, avoid
    premature enforcement of an untested edge case).

    No `created_at`/`updated_at` columns — none of this module's other
    reference tables (`VoltageLevel`, `Region`, `State`, `GridOwner`,
    `OperationalStatus`, `LineType`) have them either; adding them here
    alone would be an inconsistent, one-off enrichment of an otherwise
    identically-shaped table family.
    """

    __tablename__ = "transformer_breaker_numbering_convention"

    convention_id: Mapped[int] = mapped_column(_ReferenceKey, primary_key=True, autoincrement=True)
    hv_voltage_level_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("voltage_level.voltage_level_id", ondelete="RESTRICT"),
        nullable=False,
    )
    lv_voltage_level_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("voltage_level.voltage_level_id", ondelete="RESTRICT"),
        nullable=False,
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    # e.g. "H{N}0", "{N}80", "{N}T0", "3{N}" — {N} is replaced with the
    # transformer/bay number by the frontend. NULL means no suggestion.
    pattern: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_standard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("side IN ('HV', 'LV')", name="ck_transformer_breaker_convention_side"),
        UniqueConstraint(
            "hv_voltage_level_id",
            "lv_voltage_level_id",
            "side",
            name="uq_transformer_breaker_convention_pair_side",
        ),
        Index("ix_transformer_breaker_convention_hv", "hv_voltage_level_id"),
        Index("ix_transformer_breaker_convention_lv", "lv_voltage_level_id"),
    )
