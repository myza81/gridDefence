"""Substation Registry persistence models (CLAUDE.md A6 — Persistence Model
layer). Exact shape per docs/architecture/substation-registry.md §6.

`created_by_user_id`/`updated_by_user_id`/`changed_by_user_id` are real
foreign keys to IAM's `user.user_id` (ADR-002; substation-registry.md §7
notes these "REFERENCES iam.user(user_id), once IAM is implemented" — IAM is
now implemented as of Phase 1). Referenced by table-name string, not by
importing `app.modules.iam.models` — SQLAlchemy resolves the FK against the
shared `Base.metadata` at mapper-configuration time, so no cross-module
Python import is needed (CLAUDE.md A1 — no cross-module repository imports).

Architectural note (see Phase 2's final report, "Architectural issues
encountered"): substation-registry.md §6 specifies `substation_alias
.substation_id` as `ON DELETE CASCADE`, but CLAUDE.md §11.7 prohibits
cascade delete on engineering entities and defaults relationships to
`ON DELETE RESTRICT`; per the standards precedence in CLAUDE.md F1
(CLAUDE.md standards outrank module architecture documents), this model
uses `ON DELETE RESTRICT` instead. This has no behavioural effect on
anything Phase 2 actually implements: no hard-delete endpoint exists yet
(substation-registry.md §12's admin-only hard-delete exception is explicitly
out of this phase's scope), so this FK's delete behaviour is currently
unreachable either way.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Substation(Base):
    """The aggregate root — the only entity external modules may reference
    (substation-registry.md §4). Identity, static/slowly-changing
    engineering metadata, and lifecycle status of a substation as a
    physical asset.
    """

    __tablename__ = "substation"

    substation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    mnemonic: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    official_name: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)

    # Deprecated (ADR-009): a substation's voltage level(s) are now
    # represented exclusively by SubstationVoltageYard (ADR-008, owned by
    # Equipment Registry). This column is nullable legacy data only — no
    # longer read, written, or validated by any live code path in this
    # module (see service.py). Retained rather than dropped so existing
    # rows' historical values and substation_audit_log entries referencing
    # this field remain meaningful without a harder, less reversible
    # column-drop migration.
    voltage_level_id: Mapped[int | None] = mapped_column(
        SmallInteger,
        ForeignKey("voltage_level.voltage_level_id", ondelete="RESTRICT"),
        nullable=True,
    )
    region_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("region.region_id", ondelete="RESTRICT"), nullable=False
    )
    # GM Zone (Grid Maintenance Zone) — organizational maintenance
    # responsibility, independent of `region_id` (a grid-planning
    # grouping); the two are deliberately never coupled by any constraint
    # (Project Owner instruction: "Region and GM Zone ... must remain
    # separate"). NOT NULL, exactly like region_id/state_id/grid_owner_id
    # — every Substation shall reference exactly one GM Zone. (Briefly
    # nullable during initial rollout, tightened once every pre-existing
    # Substation had a valid GM Zone assigned — see migration
    # 0016_gm_zone's own docstring.)
    gm_zone_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("gm_zone.gm_zone_id", ondelete="RESTRICT"), nullable=False
    )
    # State (Malaysian state) is an *administrative* classification, not
    # part of a Substation's engineering identity (which is electrical/
    # operational — mnemonic, voltage yards, connectivity). It is therefore
    # OPTIONAL: nullable, may be omitted at creation, added later, or
    # cleared later, exactly as an administrative attribute should be
    # (substation-registry.md §"State is optional"; ADR-026). This is a
    # deliberate loosening — region_id/gm_zone_id/grid_owner_id remain
    # NOT NULL; State alone is administrative rather than identity-bearing.
    state_id: Mapped[int | None] = mapped_column(
        SmallInteger, ForeignKey("state.state_id", ondelete="RESTRICT"), nullable=True
    )
    grid_owner_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("grid_owner.grid_owner_id", ondelete="RESTRICT"), nullable=False
    )
    operational_status_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("operational_status.operational_status_id", ondelete="RESTRICT"),
        nullable=False,
    )

    psse_bus_number: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    commissioned_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Accountability — real FKs to IAM's User (ADR-002), never free-text.
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)", name="ck_substation_lat_range"
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
            name="ck_substation_lon_range",
        ),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_substation_geo_pair",
        ),
        # Case-insensitive uniqueness (substation-registry.md §6) in addition
        # to the plain case-sensitive UNIQUE constraints on mnemonic/
        # official_name above — mirrors the pattern already established for
        # User.username in app/modules/iam/models.py.
        Index("uq_substation_mnemonic_ci", func.lower(mnemonic), unique=True),
        Index("uq_substation_name_ci", func.lower(official_name), unique=True),
        Index("ix_substation_region", "region_id"),
        Index("ix_substation_gm_zone", "gm_zone_id"),
        Index("ix_substation_state", "state_id"),
        Index("ix_substation_voltage", "voltage_level_id"),
        Index("ix_substation_owner", "grid_owner_id"),
        Index("ix_substation_status", "operational_status_id"),
    )


class SubstationAlias(Base):
    """Historical mnemonics/names a substation has held
    (substation-registry.md §4). A mnemonic change writes one row here
    preserving the retired value — never overwritten in place.
    """

    __tablename__ = "substation_alias"

    alias_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    substation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation.substation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    alias_mnemonic: Mapped[str | None] = mapped_column(String(10), nullable=True)
    alias_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "alias_mnemonic IS NOT NULL OR alias_name IS NOT NULL", name="ck_alias_has_value"
        ),
        Index("ix_substation_alias_lookup", "alias_mnemonic"),
    )


class SubstationAuditLog(Base):
    """Append-only record of attribute changes to a `Substation`
    (substation-registry.md §4, §8 rule 8) — one row per changed field.
    Protects historical integrity (CLAUDE.md §5.2, §5.4).
    """

    __tablename__ = "substation_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    substation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation.substation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (Index("ix_audit_substation_time", "substation_id", changed_at.desc()),)
