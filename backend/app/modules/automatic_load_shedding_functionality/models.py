"""Automatic Load Shedding Functionality Registry persistence models
(CLAUDE.md A6 — Persistence Model layer). Shape per
docs/architecture/automatic-load-shedding-functionality-registry-module.md
§5, §7, §11 (ADR-011).

This module owns exactly one entity family: the per-Bay-Terminal record of
whether automatic UFLS and/or UVLS shedding functionality is installed,
wired, configured, commissioned, and available, plus its own lifecycle and
audit trail. It is **not** a general relay asset-management model (EDR-003;
ADR-011 §3) — `relay_make`/`relay_model` are optional, secondary metadata
only.

`circuit_terminal`/`transformer_terminal` (from
`app.modules.equipment_registry.models`) are imported read-only here,
exactly as `Substation`/`SubstationVoltageYard` already are elsewhere in
this codebase — this module never writes to Equipment Registry's tables
(CLAUDE.md A1; module document §4).

`created_by_user_id`/`updated_by_user_id`/`changed_by_user_id` are real
foreign keys to IAM's `user.user_id` (ADR-002), referenced by table-name
string — no cross-module Python import needed (CLAUDE.md A1).
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
    String,
    Text,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AutomaticLoadSheddingFunctionality(Base):
    """One record per Bay Terminal (module document §5, §7) — a
    `CircuitTerminal` (line/circuit bay) or a `TransformerTerminal`
    (transformer bay), never both, never neither (§11's database-enforced
    XOR). Records whether automatic UFLS and/or UVLS shedding functionality
    is installed and ready, its own independent lifecycle status, optional
    secondary relay metadata, and free-text remarks.

    `lifecycle_status` and `target_type` are modeled as `CHECK`-constrained
    strings rather than reference tables — both enumerations are small,
    stable, and internal to this module alone, not cross-module Core
    Platform reference data (module document §11, mirroring
    `TopologyVersion.status`'s own precedent in `psse_integration/models.py`).

    Current-state master data with a full audit trail, not the Canonical
    Version Lifecycle (CLAUDE.md A3) — module document §8, mirroring
    `Circuit`/`Transformer`/`SubstationVoltageYard`'s own classification
    (CLAUDE.md §11.5).
    """

    __tablename__ = "automatic_load_shedding_functionality"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    circuit_terminal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("circuit_terminal.circuit_terminal_id", ondelete="RESTRICT"),
        nullable=True,
    )
    transformer_terminal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("transformer_terminal.transformer_terminal_id", ondelete="RESTRICT"),
        nullable=True,
    )

    ufls_function: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    uvls_function: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Status Model Refinement (engineering refinement, superseding the
    # earlier ACTIVE<->INACTIVE->DECOMMISSIONED design): the *persisted*
    # lifecycle is now binary — a record exists (`ACTIVE`) until it is
    # permanently decommissioned (`DECOMMISSIONED`, terminal). There is no
    # longer a manually-toggled "temporarily unavailable" state.
    #
    # This column is deliberately NOT the three-value status ("Available" /
    # "Assigned" / "Decommissioned") an engineer sees on the registry page.
    # "Available" vs "Assigned" is never stored here — it is computed at
    # read time by the service layer from whether the terminal is
    # currently referenced by an active UFLS/UVLS scheme (supplied by a
    # future caller; see service.py's module docstring). Renamed from the
    # earlier `status` to make this persisted/computed split explicit and
    # prevent the two concepts from being confused in code or in the API.
    lifecycle_status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    # Optional, secondary metadata only (EDR-003; module document §3) —
    # never required, never this registry's subject matter.
    relay_make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    relay_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
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
            "target_type IN ('CIRCUIT_TERMINAL','TRANSFORMER_TERMINAL')",
            name="ck_alsf_target_type",
        ),
        CheckConstraint(
            "lifecycle_status IN ('ACTIVE','DECOMMISSIONED')",
            name="ck_alsf_lifecycle_status",
        ),
        # Exactly one target terminal per record — mirrors
        # ck_equipment_topology_map_target_xor / ck_load_snapshot_element_
        # state_xor (psse_integration/models.py), the same established
        # two-way XOR pattern, applied here for consistency (ADR-011 §2;
        # module document §11).
        CheckConstraint(
            "(target_type = 'CIRCUIT_TERMINAL' AND circuit_terminal_id IS NOT NULL "
            "AND transformer_terminal_id IS NULL) "
            "OR "
            "(target_type = 'TRANSFORMER_TERMINAL' AND transformer_terminal_id IS NOT NULL "
            "AND circuit_terminal_id IS NULL)",
            name="ck_alsf_target_xor",
        ),
        # A record with no function at all represents nothing (module
        # document §10 — business rule 3).
        CheckConstraint(
            "ufls_function IS TRUE OR uvls_function IS TRUE",
            name="ck_alsf_function_flags",
        ),
        # At most one non-decommissioned record per terminal (module
        # document §9 rule 2, §11) — portable partial unique index, mirroring
        # iam/models.py's own `uq_user_role_active`/`uq_external_identity_
        # active` precedent (enforced on both PostgreSQL and SQLite).
        Index(
            "uq_alsf_circuit_terminal_active",
            "circuit_terminal_id",
            unique=True,
            postgresql_where=text(
                "lifecycle_status != 'DECOMMISSIONED' AND circuit_terminal_id IS NOT NULL"
            ),
            sqlite_where=text(
                "lifecycle_status != 'DECOMMISSIONED' AND circuit_terminal_id IS NOT NULL"
            ),
        ),
        Index(
            "uq_alsf_transformer_terminal_active",
            "transformer_terminal_id",
            unique=True,
            postgresql_where=text(
                "lifecycle_status != 'DECOMMISSIONED' AND transformer_terminal_id IS NOT NULL"
            ),
            sqlite_where=text(
                "lifecycle_status != 'DECOMMISSIONED' AND transformer_terminal_id IS NOT NULL"
            ),
        ),
        Index("ix_alsf_circuit_terminal", "circuit_terminal_id"),
        Index("ix_alsf_transformer_terminal", "transformer_terminal_id"),
        Index("ix_alsf_lifecycle_status", "lifecycle_status"),
        Index("ix_alsf_ufls_function", "ufls_function"),
        Index("ix_alsf_uvls_function", "uvls_function"),
    )


class AutomaticLoadSheddingFunctionalityAuditLog(Base):
    """Append-only record of changes to an `AutomaticLoadSheddingFunctionality`
    record — every lifecycle transition and metadata edit (module document
    §5, §14; CLAUDE.md A4), one row per changed field, mirroring
    `SubstationAuditLog`'s/`TransformerAuditLog`'s own established pattern.
    """

    __tablename__ = "automatic_load_shedding_functionality_audit_log"

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    functionality_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("automatic_load_shedding_functionality.id", ondelete="RESTRICT"),
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
            "ix_alsf_audit_functionality_time",
            "functionality_id",
            changed_at.desc(),
        ),
    )
