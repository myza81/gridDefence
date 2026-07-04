"""Equipment Registry persistence models (CLAUDE.md A6 — Persistence Model
layer). Circuit / CircuitTerminal / SubstationVoltageYard shape per
docs/architecture/equipment-registry-module.md §7.4–§7.6, §7.5a, §11
(ADR-006, ADR-007, ADR-008).

Scope note (see this phase's implementation report, "Architectural issues
encountered"): the full specification frames `CircuitTerminal` as a
per-`Equipment`-row detail table sharing a common `Equipment` backbone with
`LoadTransformerDetail`/`AutoTransformerDetail`/`RelayDetail` (§7.1, §7.5).
Phase 3 implemented Circuit & CircuitTerminal Management only — no other
`equipment_type` existed yet. Building a four-way polymorphic backbone table
for a single, then-only consumer would have been premature abstraction
(CLAUDE.md §21). `CircuitTerminal` therefore carries its own identity
(`circuit_terminal_id`) directly rather than sitting on a separate
`Equipment` row.

**Phase 3.5 update:** `Transformer`/`TransformerTerminal` is exactly the
"future phase adds LoadTransformer/AutoTransformer" trigger this note
anticipated — and the shared `Equipment` backbone is still **deliberately
not** introduced, per this phase's own explicit scope guardrails (no
generalized `Equipment` backbone). `TransformerTerminal` therefore also
carries its own identity (`transformer_terminal_id`) directly, exactly
mirroring `CircuitTerminal`'s own choice. The backbone note above remains
accurate for whenever a `Relay` (or a third equipment type) is eventually
added — it does not require any change to the business rules enforced by
either terminal type here.

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
    # Correction model (Phase 3 follow-up): reused from the same Core
    # Platform `operational_status` table every other entity in this module
    # already uses (CLAUDE.md §11.3) — never a dedicated boolean/enum.
    # Normally ACTIVE; set to ENTERED_IN_ERROR to correct a mistakenly-
    # created switchyard without a hard delete (CLAUDE.md §11.6). See
    # EquipmentRegistryService.update_voltage_yard's docstring for the
    # reference-protection rule enforced when correcting a switchyard.
    operational_status_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("operational_status.operational_status_id", ondelete="RESTRICT"),
        nullable=False,
    )

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
        Index("ix_substation_voltage_yard_status", "operational_status_id"),
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
    # Correction model (Phase 3 follow-up): reused from the shared Core
    # Platform `operational_status` table (CLAUDE.md §11.3). Normally
    # ACTIVE; set to ENTERED_IN_ERROR to correct a mistakenly-added
    # terminal without a hard delete and without disturbing the rest of
    # the circuit's history — the row is never removed, only hidden from
    # default list/summary views (EquipmentRegistryService.update_terminal,
    # list_circuits). Unlike a switchyard, no reference-protection check is
    # needed here — nothing else references a CircuitTerminal.
    operational_status_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("operational_status.operational_status_id", ondelete="RESTRICT"),
        nullable=False,
    )

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
        Index("ix_circuit_terminal_status", "operational_status_id"),
    )


class Transformer(Base):
    """A two-winding or auto-transformer connecting exactly two switchyards
    at different voltage levels (Phase 3.5 — Transformer Registry). Tertiary
    winding, impedance, tap-changer modelling, loading, and protection relay
    modelling are explicitly out of scope for this phase — this entity
    deliberately does not distinguish a physical auto-transformer from a
    conventional two-winding one; both are "two switchyards plus a number"
    here.

    **UAT correction (Phase 3.5, post-implementation):** a transformer is
    substation-owned equipment — the Malaysian transmission/distribution
    domain does not model a transformer as spanning two different
    substations. `substation_id` is therefore stored directly on
    `Transformer` (not merely derivable by joining through a terminal's own
    `SubstationVoltageYard`), and both of its `TransformerTerminal` rows
    must resolve to a `SubstationVoltageYard` under this same
    `substation_id` — enforced at the service layer on creation.

    **UAT correction #2 (post-Phase-3.5-acceptance):** the uniqueness key is
    scoped to `(substation_id, transformer_number)` alone — no longer, as an
    earlier UAT correction briefly made it. Real Malaysian grid practice
    numbers transformer bays *per transformation level*, not per substation
    as a whole: a substation legitimately has a "Transformer Bay 1" on its
    275/132kV pair *and a separate* "Transformer Bay 1" on its 132/33kV
    pair. Collapsing uniqueness to `(substation_id, transformer_number)`
    wrongly rejected the second one. Uniqueness is therefore enforced at the
    service layer once again, scoped to `(substation_id, hv_switchyard_id,
    lv_switchyard_id, transformer_number)` — i.e. the transformer's own
    substation plus both its terminals' switchyards plus its number — not as
    a raw single-table database constraint, because `hv_switchyard_id`/
    `lv_switchyard_id` live on the two child `TransformerTerminal` rows, not
    on this table. Denormalizing them onto `Transformer` merely to obtain a
    single-table constraint was considered and rejected: it would
    reintroduce the exact two-winding-only assumption Decision 1 (see the
    ADR-008 addendum) deliberately avoided baking into this table's own
    column set, for the same future-tertiary-winding reason. See the
    ADR-008 addendum's second UAT-correction entry for the full record.

    Mirrors `Circuit`'s own shape and scope decisions closely:

    - Its own identity (`transformer_id`), not a shared `Equipment` backbone
      row — same scope note as `CircuitTerminal` below. Phase 3.5 is itself
      the "future phase adds LoadTransformer/AutoTransformer" trigger that
      note anticipated; the backbone is still deliberately deferred per
      this phase's explicit scope guardrails.
    - `transformer_number` is a bay/transformer *designator* only ("1",
      "2", "Main"), never a route/name description — same semantics as
      `Circuit.bay_number` (equipment-registry-module.md §7.6). Locally
      meaningful within one substation-and-transformation-pair only (e.g.
      "1" may legitimately exist twice at the same substation, once per
      transformation pair, and also at a different substation entirely).
    - The engineering short name ("T1", "SGT1", "XGT2") is deliberately not
      stored — computed at read time from the HV terminal's voltage level
      and `transformer_number`, exactly like `Circuit.circuit_name`. See
      the ADR-008 addendum for the full decision.
    """

    __tablename__ = "transformer"

    transformer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # A transformer belongs to exactly one substation (UAT correction —
    # transformers are not modeled as spanning substations). Both terminals'
    # switchyards must resolve to this same substation_id (service layer).
    substation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation.substation_id", ondelete="RESTRICT"),
        nullable=False,
    )
    transformer_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity_mva: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    commissioning_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    operational_status_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("operational_status.operational_status_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Free text, not a reference table (unlike Circuit.line_type_id) —
    # nothing in this phase's spec defines a closed set of transformer
    # types; a reference table can be introduced later without data loss
    # if one emerges (CLAUDE.md §11.3 governs closed enumerations, not
    # every optional descriptive field).
    transformer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
        CheckConstraint(
            "capacity_mva IS NULL OR capacity_mva > 0", name="ck_transformer_capacity_positive"
        ),
        # No single-table UNIQUE constraint here (UAT correction #2) — the
        # uniqueness key is (substation_id, hv_switchyard_id, lv_switchyard_id,
        # transformer_number), and the two switchyard ids live on the child
        # TransformerTerminal rows, not this table. Enforced at the service
        # layer (EquipmentRegistryService.create_transformer/update_transformer),
        # mirroring this same table's pre-UAT-correction-#1 original design.
        Index("ix_transformer_substation", "substation_id"),
        Index("ix_transformer_status", "operational_status_id"),
        Index("ix_transformer_number", "transformer_number"),
    )


class TransformerTerminal(Base):
    """One winding-side connection point of a `Transformer` — HV or LV
    (Phase 3.5). Exactly two rows per transformer, created atomically with
    it and never added-to afterward — unlike `CircuitTerminal`, a
    transformer is never a tee-off.

    Connects to a `SubstationVoltageYard`, exactly like `CircuitTerminal`
    (ADR-008) — never directly to a `Substation`. `side` is a small,
    closed, internal vocabulary (not Core Platform reference data — it is
    intrinsic to this table's own meaning, not a cross-module lookup),
    expressed as a CHECK-constrained string rather than a separate
    reference table, so that a future tertiary-winding phase can add a
    third `side` value with a constraint change alone — no new column, no
    migration to `Transformer` itself (the decision basis for choosing this
    shape over direct `hv_*`/`lv_*` columns on `Transformer` — see the
    ADR-008 addendum).

    **UAT correction:** this row's `voltage_yard_id` must resolve to a
    `SubstationVoltageYard` whose own `substation_id` equals the parent
    `Transformer.substation_id` — enforced at the service layer on
    creation, not by a database constraint (a cross-table equality check
    spanning `TransformerTerminal` → `SubstationVoltageYard` → `Transformer`
    is not expressible as a single-table `CHECK`/`FK` constraint).
    """

    __tablename__ = "transformer_terminal"

    transformer_terminal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    transformer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transformer.transformer_id", ondelete="RESTRICT"),
        nullable=False,
    )
    side: Mapped[str] = mapped_column(String(10), nullable=False)
    voltage_yard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation_voltage_yard.voltage_yard_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Unlike CircuitTerminal's breaker_number, this one is always backed by
    # a computed suggestion offered in the UI (equipment-registry-module.md
    # transformer breaker-number convention) — the backend never validates
    # its format and never rejects a user override (deliberate; see
    # service.py).
    breaker_number: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (
        # At most one HV and one LV terminal per transformer. The full
        # completeness rule ("exactly one of each, exactly two total") is
        # enforced at the service layer on creation — mirrors Circuit's own
        # "at least two terminals" rule not being a raw DB constraint
        # either (equipment-registry-module.md §9 rule 5).
        UniqueConstraint("transformer_id", "side", name="uq_transformer_terminal_side"),
        CheckConstraint("side IN ('HV', 'LV')", name="ck_transformer_terminal_side"),
        Index("ix_transformer_terminal_transformer", "transformer_id"),
        Index("ix_transformer_terminal_voltage_yard", "voltage_yard_id"),
    )


class TransformerAuditLog(Base):
    """Append-only record of changes to a `Transformer`, including its
    terminals' breaker numbers (equipment-registry-module.md §14; CLAUDE.md
    A4) — one row per changed field, mirroring `EquipmentRegistryAuditLog`'s
    own pattern for `Circuit`. A separate table, not a shared one:
    `Circuit` and `Transformer` are separate aggregate roots, each auditing
    its own changes.
    """

    __tablename__ = "transformer_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    transformer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transformer.transformer_id", ondelete="RESTRICT"),
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

    __table_args__ = (
        Index("ix_transformer_audit_transformer_time", "transformer_id", changed_at.desc()),
    )


class SubstationVoltageYardAuditLog(Base):
    """Append-only record of changes to a `SubstationVoltageYard`
    (equipment-registry-module.md §14; CLAUDE.md A4) — added by the
    deletion/correction policy (Phase 3 follow-up) specifically so a
    switchyard's `operational_status_id` correction (Entered in Error) is
    auditable, mirroring `EquipmentRegistryAuditLog`'s and
    `TransformerAuditLog`'s own per-field pattern. Prior metadata edits
    (`commissioning_date`/`latitude`/`longitude`) predate this table and
    remain tracked only via `updated_at`/`updated_by_user_id`, per this
    module's previously-documented known limitation — this table is not
    retrofitted onto those fields as part of this policy.
    """

    __tablename__ = "substation_voltage_yard_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    voltage_yard_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation_voltage_yard.voltage_yard_id", ondelete="RESTRICT"),
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

    __table_args__ = (
        Index(
            "ix_substation_voltage_yard_audit_yard_time",
            "voltage_yard_id",
            changed_at.desc(),
        ),
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
