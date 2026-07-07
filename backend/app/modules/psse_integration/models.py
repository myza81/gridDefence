"""PSS/E Integration persistence models (CLAUDE.md A6 — Persistence Model
layer). Shape per docs/architecture/psse-integration-module.md §5/§8a/§11,
[ADR-003](../../../../docs/adr/ADR-003-psse-topology-and-load-snapshot-separation.md)
(topology/load separation),
[ADR-006](../../../../docs/adr/ADR-006-connectivity-registry-vs-psse-topology-architecture.md)
and [ADR-007](../../../../docs/adr/ADR-007-canonical-engineering-reference-object.md)
(`EquipmentTopologyMap`).

**Topology vs. load separation (ADR-003) is structural, not just a naming
convention:** `TopologyBus`/`TopologyBranch`/`TopologyTransformer` carry no
P/Q, voltage-magnitude/angle, or in-service/operational-state field
anywhere — that data lives exclusively on `LoadSnapshotBusState`/
`LoadSnapshotElementState`/`NetworkLoad`/`NetworkGenerator`, each scoped to
one `LoadSnapshot`. This guarantees, by construction, that momentary
operational state can never leak into the topology signature (§ signature.py)
— not merely a rule the signature-computation code has to remember.

`Circuit`/`CircuitTerminal` (from `app.modules.equipment_registry.models`)
are imported read-only here, exactly as `Substation` already is — this
module never writes to Equipment Registry's tables (ADR-006 §8;
psse-integration-module.md §8a.6, §9 rule 14).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base

# JSONB on PostgreSQL (indexable, binary-stored), plain JSON elsewhere
# (SQLite test stand-in) — mirrors this project's existing dialect-variant
# pattern (`_ReferenceKey` in app/reference_data/models.py) rather than
# introducing a new one.
_JsonVariant = JSON().with_variant(JSONB(), "postgresql")


class RawFileImportBatch(Base):
    """The audit/traceability record of one import action (psse-integration-
    module.md §5) — created on every upload/commit, regardless of outcome.
    Never mutated after reaching a terminal `status` (§8.1); a corrected
    import is always a new batch, never an edit to this one.
    """

    __tablename__ = "raw_file_import_batch"

    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_file_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=False
    )
    # FULL_TOPOLOGY_WITH_LOAD | LOAD_ONLY — detected purely from parsed
    # content (bus-record count), never from filename or user assertion
    # (psse-integration-module.md §10; ADR-003's own "never by user
    # assertion" principle for signature reuse, applied identically here to
    # import-type detection).
    import_type: Mapped[str] = mapped_column(String(30), nullable=False)
    computed_signature: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # `use_alter=True`: `raw_file_import_batch` <-> `topology_version` <->
    # `load_snapshot` is a genuine 3-table FK cycle (each TopologyVersion/
    # LoadSnapshot points back at the batch it was created from, and a
    # batch points forward at the TopologyVersion/LoadSnapshot it produced,
    # set only after those rows exist). `use_alter` breaks the cycle for
    # DDL ordering by emitting these two FKs as separate ALTER TABLE
    # statements after all three tables exist (see the Alembic migration).
    topology_version_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "topology_version.topology_version_id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_raw_file_import_batch_topology_version",
        ),
        nullable=True,
    )
    load_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "load_snapshot.load_snapshot_id",
            ondelete="RESTRICT",
            use_alter=True,
            name="fk_raw_file_import_batch_load_snapshot",
        ),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    # Structured list of warning dicts (e.g. unmatched bus/load, ignored
    # section) — CLAUDE.md A9: structured, not free text.
    warnings: Mapped[list] = mapped_column(_JsonVariant, nullable=False, default=list)
    fatal_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "import_type IN ('FULL_TOPOLOGY_WITH_LOAD', 'LOAD_ONLY')",
            name="ck_raw_file_import_batch_type",
        ),
        CheckConstraint(
            "status IN ('Parsing', 'Completed', 'CompletedWithWarnings', 'Failed')",
            name="ck_raw_file_import_batch_status",
        ),
        Index("ix_raw_file_import_batch_status", "status"),
        Index("ix_raw_file_import_batch_topology_version", "topology_version_id"),
    )


class TopologyVersion(Base):
    """An immutable network structure, identified by a deterministic
    topology signature (ADR-003; psse-integration-module.md §8.2). Lighter
    `Imported -> Current -> Superseded` lifecycle — deliberately not the
    Canonical Version Lifecycle (CLAUDE.md A3); see §9 rule 1.
    """

    __tablename__ = "topology_version"

    topology_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    signature: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_from_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("raw_file_import_batch.batch_id", ondelete="RESTRICT"),
        nullable=False,
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('Imported', 'Current', 'Superseded')",
            name="ck_topology_version_status",
        ),
        Index("ix_topology_version_status", "status"),
    )


class TopologyBus(Base):
    """A structural bus definition within a `TopologyVersion` (psse-
    integration-module.md §5, §11). No in-service, voltage-magnitude, or
    voltage-angle field — that is per-`LoadSnapshot` state
    (`LoadSnapshotBusState`), never structural (ADR-003; see module
    docstring).
    """

    __tablename__ = "topology_bus"

    topology_bus_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topology_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("topology_version.topology_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    bus_number: Mapped[int] = mapped_column(Integer, nullable=False)
    bus_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    base_kv: Mapped[float] = mapped_column(Numeric(8, 3), nullable=False)
    substation_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("substation.substation_id", ondelete="RESTRICT"),
        nullable=True,
    )
    psse_area: Mapped[int | None] = mapped_column(Integer, nullable=True)
    psse_zone: Mapped[int | None] = mapped_column(Integer, nullable=True)
    psse_owner: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        UniqueConstraint("topology_version_id", "bus_number", name="uq_topology_bus_number"),
        Index("ix_topology_bus_version", "topology_version_id"),
        Index("ix_topology_bus_substation", "substation_id"),
    )


class TopologyBranch(Base):
    """A structural transmission branch within a `TopologyVersion` — purely
    structural (from/to bus, circuit id, impedance, ratings). No in-service
    field; see module docstring."""

    __tablename__ = "topology_branch"

    topology_branch_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    topology_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("topology_version.topology_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    to_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    ckt_id: Mapped[str] = mapped_column(String(2), nullable=False)
    r: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    x: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    b: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    rate_a: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rate_b: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    rate_c: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        Index("ix_topology_branch_version", "topology_version_id"),
        Index("ix_topology_branch_from_bus", "from_bus_id"),
        Index("ix_topology_branch_to_bus", "to_bus_id"),
    )


class TopologyTransformer(Base):
    """A structural transformer within a `TopologyVersion` — 2-winding
    (`tertiary_bus_id` null) or 3-winding. Purely structural; no in-service
    field. Impedance/rating fields are deliberately minimal (primary
    winding only) — full multi-winding fidelity is out of this phase's
    scope, mirroring Equipment Registry's own `Transformer` entity, which
    likewise models only two windings (equipment-registry-module.md,
    Phase 3.5 Addendum)."""

    __tablename__ = "topology_transformer"

    topology_transformer_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    topology_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("topology_version.topology_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    from_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    to_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    tertiary_bus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=True
    )
    ckt_id: Mapped[str] = mapped_column(String(2), nullable=False)
    r: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    x: Mapped[float] = mapped_column(Numeric(12, 6), nullable=False)
    rate_a: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    __table_args__ = (
        Index("ix_topology_transformer_version", "topology_version_id"),
        Index("ix_topology_transformer_from_bus", "from_bus_id"),
        Index("ix_topology_transformer_to_bus", "to_bus_id"),
    )


class LoadSnapshot(Base):
    """An immutable capture of load/generation state, tied to exactly one
    `TopologyVersion` (ADR-003). Same lighter three-state lifecycle as
    `TopologyVersion` (§8.3)."""

    __tablename__ = "load_snapshot"

    load_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topology_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("topology_version.topology_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    created_from_batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("raw_file_import_batch.batch_id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            "status IN ('Imported', 'Current', 'Superseded')", name="ck_load_snapshot_status"
        ),
        Index("ix_load_snapshot_topology_version", "topology_version_id"),
        Index("ix_load_snapshot_status", "status"),
    )


class LoadSnapshotBusState(Base):
    """Per-`LoadSnapshot` bus state: voltage magnitude/angle, PSS/E bus
    type, and in-service status — deliberately not on `TopologyBus` itself
    (ADR-003; see module docstring)."""

    __tablename__ = "load_snapshot_bus_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    load_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("load_snapshot.load_snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    topology_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    # PSS/E IDE code: 1=load, 2=generator/PV, 3=swing, 4=isolated.
    bus_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    voltage_mag: Mapped[float | None] = mapped_column(Numeric(8, 5), nullable=True)
    voltage_angle: Mapped[float | None] = mapped_column(Numeric(8, 4), nullable=True)
    in_service: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("load_snapshot_id", "topology_bus_id", name="uq_load_snapshot_bus_state"),
        Index("ix_load_snapshot_bus_state_snapshot", "load_snapshot_id"),
    )


class LoadSnapshotElementState(Base):
    """Per-`LoadSnapshot` in-service status for a branch or transformer —
    momentary operational state, separate from the element's permanent
    structural definition (ADR-003)."""

    __tablename__ = "load_snapshot_element_state"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    load_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("load_snapshot.load_snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    topology_branch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("topology_branch.topology_branch_id", ondelete="RESTRICT"),
        nullable=True,
    )
    topology_transformer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("topology_transformer.topology_transformer_id", ondelete="RESTRICT"),
        nullable=True,
    )
    in_service: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(
            "(topology_branch_id IS NOT NULL) != (topology_transformer_id IS NOT NULL)",
            name="ck_load_snapshot_element_state_xor",
        ),
        Index("ix_load_snapshot_element_state_snapshot", "load_snapshot_id"),
    )


class NetworkLoad(Base):
    """Per-`LoadSnapshot` load record at a bus (P MW, Q MVAr). `load_id`
    disambiguates multiple loads at the same bus (PSS/E convention, e.g.
    '1', 'T1', 'F2')."""

    __tablename__ = "network_load"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    load_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("load_snapshot.load_snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    topology_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    load_id: Mapped[str] = mapped_column(String(2), nullable=False)
    p_mw: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)
    q_mvar: Mapped[float] = mapped_column(Numeric(10, 3), nullable=False)

    __table_args__ = (
        UniqueConstraint("load_snapshot_id", "topology_bus_id", "load_id", name="uq_network_load"),
        Index("ix_network_load_snapshot", "load_snapshot_id"),
    )


class NetworkGenerator(Base):
    """Per-`LoadSnapshot` generator record at a bus (P/Q generation and
    limits)."""

    __tablename__ = "network_generator"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    load_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("load_snapshot.load_snapshot_id", ondelete="RESTRICT"),
        nullable=False,
    )
    topology_bus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("topology_bus.topology_bus_id", ondelete="RESTRICT"), nullable=False
    )
    gen_id: Mapped[str] = mapped_column(String(2), nullable=False)
    p_gen: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    q_gen: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    p_max: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    p_min: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    q_max: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    q_min: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "load_snapshot_id", "topology_bus_id", "gen_id", name="uq_network_generator"
        ),
        Index("ix_network_generator_snapshot", "load_snapshot_id"),
    )


class EquipmentTopologyMap(Base):
    """Correlates one `CircuitTerminal` (Equipment Registry, read-only
    reference — never a `Circuit` id directly, never a generic `Equipment`
    id, per ADR-007 §6/§9/§12 item 5) to the `TopologyBranch`/
    `TopologyTransformer` element it resolves to within one
    `TopologyVersion` (psse-integration-module.md §8a).

    At most one row per `(topology_version_id, circuit_terminal_id)` —
    recomputation (e.g. after an Equipment Registry correction, or a later
    import against the same `TopologyVersion`) updates this row in place
    rather than creating a parallel history row; the historical record of
    each computation event lives in `psse_import_audit_log` (§8a.8), not as
    multiple `EquipmentTopologyMap` rows for the same pair.

    **This table is never written to as a side effect of correcting
    Equipment Registry, and never itself writes to Equipment Registry** —
    matching is one-directional (this table -> Equipment Registry, read
    only) and correction is one-directional the other way (an accepted
    discrepancy is written through Equipment Registry's own service layer,
    never from here) — psse-integration-module.md §8a.6, §9 rule 14.
    """

    __tablename__ = "equipment_topology_map"

    map_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topology_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("topology_version.topology_version_id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Read-only reference to Equipment Registry's CircuitTerminal — never
    # written to from this module (see class docstring).
    circuit_terminal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("circuit_terminal.circuit_terminal_id", ondelete="RESTRICT"),
        nullable=False,
    )
    topology_branch_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("topology_branch.topology_branch_id", ondelete="RESTRICT"),
        nullable=True,
    )
    topology_transformer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("topology_transformer.topology_transformer_id", ondelete="RESTRICT"),
        nullable=True,
    )
    match_outcome: Mapped[str] = mapped_column(String(20), nullable=False)
    discrepancy_resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    resolved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "match_outcome IN ('clean_match', 'unmatched', 'discrepancy')",
            name="ck_equipment_topology_map_outcome",
        ),
        CheckConstraint(
            "discrepancy_resolution IS NULL OR discrepancy_resolution IN ('accepted', 'rejected')",
            name="ck_equipment_topology_map_resolution",
        ),
        # At most one of branch/transformer set; both null when unmatched.
        CheckConstraint(
            "NOT (topology_branch_id IS NOT NULL AND topology_transformer_id IS NOT NULL)",
            name="ck_equipment_topology_map_target_xor",
        ),
        UniqueConstraint(
            "topology_version_id", "circuit_terminal_id", name="uq_equipment_topology_map_terminal"
        ),
        Index("ix_equipment_topology_map_version", "topology_version_id"),
        Index("ix_equipment_topology_map_outcome", "match_outcome"),
    )


class PsseImportAuditLog(Base):
    """PSS/E Integration's own audit trail (CLAUDE.md A4), covering every
    entity in this module — import batches, activations, and
    `EquipmentTopologyMap` computations/resolutions (psse-integration-
    module.md §14). `changed_by_user_id` is nullable: an automated match
    computation (`equipment_match_computed`) has no human actor, mirroring
    network-model-module.md §14's own logged-vs-audited distinction for
    automated calculations."""

    __tablename__ = "psse_import_audit_log"

    log_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # 80 chars, not 64: EquipmentTopologyMap's own audit entries key on a
    # composite "{topology_version_id}:{circuit_terminal_id}" (2 UUIDs +
    # separator = 73 chars) — caught by a real PostgreSQL run (SQLite does
    # not enforce VARCHAR length, so this only surfaced there).
    entity_id: Mapped[str] = mapped_column(String(80), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    changed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("user.user_id", ondelete="RESTRICT"), nullable=True
    )
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_psse_import_audit_entity", "entity_type", "entity_id", changed_at.desc()),
    )
