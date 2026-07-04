"""Equipment Registry persistence models (CLAUDE.md A6 — Persistence Model
layer). Circuit / CircuitTerminal / SubstationVoltageYard shape per
docs/architecture/equipment-registry-module.md §7.4–§7.6, §7.5a, §11
(ADR-006, ADR-007, ADR-008).

Scope note (see this phase's implementation report, "Architectural issues
encountered"): the full specification frames `CircuitTerminal` as a
per-`Equipment`-row detail table sharing a common `Equipment` backbone with
`LoadTransformerDetail`/`AutoTransformerDetail`/`RelayDetail` (§7.1, §7.5).
This phase implements Circuit & CircuitTerminal Management only — no other
`equipment_type` exists yet, and nothing in this phase's scope references
transformers or relays. Building a four-way polymorphic backbone table for a
single, currently-only consumer would be premature abstraction (CLAUDE.md
§21). `CircuitTerminal` therefore carries its own identity
(`circuit_terminal_id`) directly rather than sitting on a separate
`Equipment` row. If/when a future phase adds `LoadTransformer`/
`AutoTransformer`/`Relay`, the shared `Equipment` backbone described in
§7.1 should be introduced then, via a migration that folds
`circuit_terminal_id` into that backbone's `equipment_id` — this does not
require any change to the business rules enforced here.

`created_by_user_id`/`updated_by_user_id`/`changed_by_user_id` are real
foreign keys to IAM's `user.user_id` (ADR-002), referenced by table-name
string — no cross-module Python import needed (CLAUDE.md A1).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Circuit(Base):
    """The canonical engineering reference object for a physical line, as a
    whole (equipment-registry-module.md §7.4; ADR-007 §6, §10) — the object
    defence schemes, compliance, and dashboards will reference.
    """

    __tablename__ = "circuit"

    circuit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # The circuit-level human designator ("Line 1", "Line 2") — a property of
    # the whole circuit, not of one terminal (§7.6).
    bay_number: Mapped[str] = mapped_column(String(20), nullable=False)

    voltage_level_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("voltage_level.voltage_level_id", ondelete="RESTRICT"),
        nullable=False,
    )
    line_type_id: Mapped[int] = mapped_column(
        SmallInteger, ForeignKey("line_type.line_type_id", ondelete="RESTRICT"), nullable=False
    )
    operational_status_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("operational_status.operational_status_id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_interconnector: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        Index("ix_circuit_voltage_level", "voltage_level_id"),
        Index("ix_circuit_line_type", "line_type_id"),
        Index("ix_circuit_status", "operational_status_id"),
        Index("ix_circuit_bay_number", "bay_number"),
    )


class SubstationVoltageYard(Base):
    """One voltage level physically present at a substation
    (equipment-registry-module.md §7.5a; ADR-008). A multi-voltage
    substation (e.g. PKLG with both a 275kV yard and a 132kV yard) has more
    than one row; a single-voltage substation has exactly one.

    Owned by Equipment Registry, not Substation Registry (ADR-008) — it
    asserts a wiring-level fact ("equipment terminates at this substation
    at this voltage"), not a new fact about substation identity, geography,
    or operational status, all of which remain exclusively owned by
    Substation Registry. No substation attributes are copied here
    (CLAUDE.md §5.1) — only `substation_id` is referenced, by foreign key.
    """

    __tablename__ = "substation_voltage_yard"

    voltage_yard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    substation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation.substation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    voltage_level_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("voltage_level.voltage_level_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Yard-level metadata (Phase 3 UAT follow-up) — deliberately NOT on
    # Substation: a multi-voltage site may have yards commissioned at
    # different dates with slightly different GIS coordinates (e.g. two
    # physically separate switchyards on the same site). All optional.
    commissioning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    # Added alongside metadata editability — mirrors CircuitTerminal's own
    # updated_at/updated_by_user_id (see 0005_substation_voltage_yard.py).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        # At most one yard per substation per voltage level (§7.5a).
        UniqueConstraint("substation_id", "voltage_level_id", name="uq_substation_voltage_yard"),
        Index("ix_substation_voltage_yard_substation", "substation_id"),
        Index("ix_substation_voltage_yard_voltage_level", "voltage_level_id"),
        # Mirrors Substation's own lat/lon validation exactly
        # (substation_registry/models.py) — same conceptual fields, now
        # also carried at yard granularity.
        CheckConstraint(
            "latitude IS NULL OR (latitude BETWEEN -90 AND 90)",
            name="ck_voltage_yard_lat_range",
        ),
        CheckConstraint(
            "longitude IS NULL OR (longitude BETWEEN -180 AND 180)",
            name="ck_voltage_yard_lon_range",
        ),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_voltage_yard_geo_pair",
        ),
    )


class CircuitTerminal(Base):
    """One voltage yard's end of a `Circuit` (equipment-registry-module.md
    §7.5). Two or more rows share the same `circuit_id` for a single
    physical line — an ordinary circuit has exactly two; a tee-off has
    three or more, using the same table with no special-cased mechanism.

    Connects to a `SubstationVoltageYard`, not directly to a `Substation`
    (ADR-008) — a multi-voltage substation cannot be disambiguated by
    `substation_id` alone. A terminal's substation is
    `SubstationVoltageYard.substation_id`, one join away.
    """

    __tablename__ = "circuit_terminal"

    circuit_terminal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    circuit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("circuit.circuit_id", ondelete="RESTRICT"), nullable=False
    )
    voltage_yard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation_voltage_yard.voltage_yard_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Terminal-specific, independently numbered — never the same field as
    # Circuit.bay_number (§7.6).
    breaker_number: Mapped[str] = mapped_column(String(20), nullable=False)
    commissioning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    # Added alongside terminal editability (breaker_number/commissioning_date/
    # remarks) — mirrors Circuit's own updated_at/updated_by_user_id.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        # Business rule 6 (equipment-registry-module.md §9): no voltage yard
        # may hold more than one terminal of the same circuit — restated at
        # voltage-yard, not substation, granularity per ADR-008.
        UniqueConstraint("circuit_id", "voltage_yard_id", name="uq_circuit_terminal_voltage_yard"),
        Index("ix_circuit_terminal_circuit", "circuit_id"),
        Index("ix_circuit_terminal_voltage_yard", "voltage_yard_id"),
    )


class EquipmentRegistryAuditLog(Base):
    """Append-only record of changes to a `Circuit`, including terminal
    additions (equipment-registry-module.md §5, §14; CLAUDE.md A4) — one
    row per changed field, mirroring Substation Registry's own
    `substation_audit_log` pattern (`SubstationAuditLog`).
    """

    __tablename__ = "equipment_registry_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    circuit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("circuit.circuit_id", ondelete="RESTRICT"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_equipment_registry_audit_circuit_time", "circuit_id", changed_at.desc()),
    )
