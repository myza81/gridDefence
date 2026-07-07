"""PSS/E Integration service layer (CLAUDE.md §14) — business rules,
orchestration, and audit writing live here, and only here.

Implements psse-integration-module.md's workflows 1-8 (§8.4-§8.11), the
`EquipmentTopologyMap` specification (§8a), and ADR-003's topology/load
separation. Never calls `self.db.commit()` — the caller (router, or the
job wrapper in `jobs.py`) owns the transaction boundary, mirroring every
other module's service layer in this codebase.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.modules.equipment_registry.models import Circuit, CircuitTerminal, SubstationVoltageYard
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.modules.psse_integration.exceptions import (
    BatchNotActivatableError,
    DiscrepancyAlreadyResolvedError,
    NoCurrentTopologyVersionError,
    NotFoundError,
    RawFileParseError,
)
from app.modules.psse_integration.matching import (
    TerminalCandidate,
    TopologyElementCandidate,
    compute_matches,
)
from app.modules.psse_integration.models import (
    EquipmentTopologyMap,
    LoadSnapshot,
    LoadSnapshotBusState,
    LoadSnapshotElementState,
    NetworkGenerator,
    NetworkLoad,
    PsseImportAuditLog,
    RawFileImportBatch,
    TopologyBranch,
    TopologyBus,
    TopologyTransformer,
    TopologyVersion,
)
from app.modules.psse_integration.raw_parser import ParsedCase, RawParseError, parse_raw
from app.modules.psse_integration.repository import PsseIntegrationRepository
from app.modules.psse_integration.schemas import (
    BatchSummary,
    CircuitCorrelation,
    CurrentStatus,
    EquipmentTopologyMapEntry,
    FindingGroup,
    LoadSnapshotSummary,
    TopologyVersionSummary,
)
from app.modules.psse_integration.signature import compute_topology_signature
from app.modules.substation_registry.models import Substation

# --- Commit engineering findings: categorization and aggregation
# (Phase 6.1 engineering presentation refinement, §8.9d) -----------------------

# Every category a Commit warning can be tagged with, and which of the
# three presentation groups it belongs to. Tagged at the point each
# warning is *constructed* (below, in `_commit_full_topology`/
# `_commit_load_only`), where its engineering meaning is already
# unambiguous — never guessed later from message text, except for the two
# categories `raw_parser.py` itself produces as plain, undifferentiated
# strings (`_categorize_parser_warning`), whose exact message shapes are
# that module's own small, stable, documented set.
_FINDING_CATEGORY_GROUPS: dict[str, str] = {
    "unmatched_bus": "engineering_review_required",
    "unmatched_branch_reference": "engineering_review_required",
    "unmatched_transformer_reference": "engineering_review_required",
    "unmatched_load_bus": "engineering_review_required",
    "unparsed_data_line": "engineering_review_required",
    "unrecognized_section": "parser_notices",
}


def _categorize_parser_warning(message: str) -> str:
    """`case.warnings` (raw_parser.py) is a plain `list[str]` with exactly
    two possible shapes today: an unrecognized-section notice, or a
    skipped/unparseable data line. Recognizing the former's own fixed,
    documented text is a stable pattern match, not a guess — see
    raw_parser.py's own `unknown_sections_warned` handling."""
    if "is not recognized by this parser" in message:
        return "unrecognized_section"
    return "unparsed_data_line"


def _summarize_finding_group(category: str, count: int) -> str:
    """Plain-language aggregate sentence for one finding category — text
    formatting only, never an engineering calculation (CLAUDE.md §21's
    "avoid premature optimisation" cousin: this composes a sentence from an
    already-known count, it does not decide anything)."""
    if category == "unmatched_bus":
        noun = "bus" if count == 1 else "buses"
        return f"{count} {noun} could not be matched to the current Substation Registry."
    if category == "unmatched_branch_reference":
        noun = "transmission line" if count == 1 else "transmission lines"
        return (
            f"{count} {noun} referenced a bus that does not exist in this file "
            "and could not be imported."
        )
    if category == "unmatched_transformer_reference":
        noun = "transformer" if count == 1 else "transformers"
        return (
            f"{count} {noun} referenced a bus that does not exist in this file "
            "and could not be imported."
        )
    if category == "unmatched_load_bus":
        noun = "load" if count == 1 else "loads"
        return f"{count} {noun} could not be matched to the current network topology."
    if category == "unrecognized_section":
        noun = "section was" if count == 1 else "sections were"
        return (
            f"{count} unsupported RAW {noun} detected. These sections are currently not "
            "required by GridDefence and were safely ignored."
        )
    noun = "data line was" if count == 1 else "data lines were"
    return f"{count} {noun} skipped because they could not be read."


def _aggregate_findings(warnings: list[dict]) -> list[FindingGroup]:
    """Groups `RawFileImportBatch.warnings` (one entry per individual
    occurrence — potentially hundreds or thousands for a large file, e.g.
    one per unmatched bus) into a small number of categorized, counted
    summaries. No new engineering fact is introduced — every message
    already exists in `warnings`; this only re-shapes them for
    presentation. `entry.get("category", ...)` falls back gracefully for
    any batch committed before this refinement, whose stored warnings
    predate category tagging."""
    messages_by_category: dict[str, list[str]] = {}
    for entry in warnings:
        category = entry.get("category") or _categorize_parser_warning(entry.get("message", ""))
        messages_by_category.setdefault(category, []).append(entry.get("message", ""))

    groups = [
        FindingGroup(
            category=category,
            group=_FINDING_CATEGORY_GROUPS.get(category, "engineering_review_required"),
            count=len(messages),
            summary=_summarize_finding_group(category, len(messages)),
            details=messages,
        )
        for category, messages in messages_by_category.items()
    ]
    # Stable, deterministic order: engineering-review-required findings
    # first (the ones most likely to need attention), then parser notices.
    group_order = {"engineering_review_required": 0, "parser_notices": 1, "informational": 2}
    groups.sort(key=lambda g: (group_order.get(g.group, 3), g.category))
    return groups


class PreviewResultData:
    """Plain, non-persisted result of a preview computation (psse-
    integration-module.md §8.9) — never a database row.

    `raw_version`/`bus_count`/`branch_count`/`transformer_count`/
    `load_count`/`generator_count` (Phase 6 engineering presentation
    refinement, §8.9b) are read directly off the already-parsed `ParsedCase`
    — no new parsing, no new database query, no new engineering
    calculation. They exist solely so the Preview page can answer "what
    operational snapshot have I uploaded" without the frontend having to
    infer network size from anything else.

    `buses`/`branches`/`transformers`/`loads`/`generators` (Operational
    Context Inspector, §8.9e) are the same `ParsedCase` lists — carried
    through unchanged so the Inspector can present them without a second
    parse or a second request.
    """

    def __init__(
        self,
        *,
        import_type: str,
        raw_version: int | None,
        bus_count: int,
        branch_count: int,
        transformer_count: int,
        load_count: int,
        generator_count: int,
        computed_signature: str | None,
        topology_reused: bool,
        matched_bus_count: int,
        unmatched_bus_count: int,
        coverage_percent: float,
        warnings: list[str],
        source_file_reference: str,
        base_mva: float | None,
        buses: list,
        branches: list,
        transformers: list,
        loads: list,
        generators: list,
    ) -> None:
        self.import_type = import_type
        self.raw_version = raw_version
        self.bus_count = bus_count
        self.branch_count = branch_count
        self.transformer_count = transformer_count
        self.load_count = load_count
        self.generator_count = generator_count
        self.computed_signature = computed_signature
        self.topology_reused = topology_reused
        self.matched_bus_count = matched_bus_count
        self.unmatched_bus_count = unmatched_bus_count
        self.coverage_percent = coverage_percent
        self.warnings = warnings
        self.source_file_reference = source_file_reference
        self.base_mva = base_mva
        self.buses = buses
        self.branches = branches
        self.transformers = transformers
        self.loads = loads
        self.generators = generators


class PsseIntegrationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = PsseIntegrationRepository(db)
        self.iam = IAMService(db)

    # --- internal helpers ---------------------------------------------------
    def _resolve_user(self, user_id: uuid.UUID | None) -> UserSummary | None:
        if user_id is None:
            return None
        return self.iam.get_user(user_id)

    def _audit(
        self,
        *,
        entity_type: str,
        entity_id: str,
        event_type: str,
        actor_user_id: uuid.UUID | None,
        change_reason: str | None = None,
    ) -> None:
        self.repo.add_audit_log(
            PsseImportAuditLog(
                entity_type=entity_type,
                entity_id=entity_id,
                event_type=event_type,
                changed_by_user_id=actor_user_id,
                change_reason=change_reason,
            )
        )

    def _match_substation_for_bus(self, bus_name: str | None) -> uuid.UUID | None:
        """Best-effort bus-to-substation matching by mnemonic prefix
        (psse-integration-module.md §9 rule 12's "unmatched buses are
        warnings only" — this module never invents or auto-creates a
        Substation Registry record; an unmatched bus simply has no
        `substation_id`). Substation mnemonics in this project are 4
        characters (e.g. `PKLG`, `IGBK`); real PSS/E bus names commonly
        embed the mnemonic plus a voltage/suffix (`PKLG132`, `SDAOFIC`) —
        matching the leading 4 characters is a deliberately simple,
        transparent heuristic, not a claim of perfect fidelity."""
        if not bus_name or len(bus_name.strip()) < 4:
            return None
        candidate_mnemonic = bus_name.strip()[:4]
        substation = self.repo.find_substation_by_mnemonic_ci(candidate_mnemonic)
        return substation.substation_id if substation is not None else None

    # --- Preview (Workflow 6, §8.9) — zero persistence ---------------------------
    def preview(self, file_content: str, source_file_reference: str) -> PreviewResultData:
        try:
            case = parse_raw(file_content)
        except RawParseError as exc:
            raise RawFileParseError(str(exc)) from exc

        warnings = list(case.warnings)
        if case.is_full_topology:
            signature = compute_topology_signature(case.buses, case.branches, case.transformers)
            existing = self.repo.find_topology_version_by_signature(signature)
            topology_reused = existing is not None
            matched = sum(1 for bus in case.buses if self._match_substation_for_bus(bus.bus_name))
            unmatched = len(case.buses) - matched
            coverage = (matched / len(case.buses) * 100.0) if case.buses else 0.0
            return PreviewResultData(
                import_type="FULL_TOPOLOGY_WITH_LOAD",
                raw_version=case.rev,
                bus_count=len(case.buses),
                branch_count=len(case.branches),
                transformer_count=len(case.transformers),
                load_count=len(case.loads),
                generator_count=len(case.generators),
                computed_signature=signature,
                topology_reused=topology_reused,
                matched_bus_count=matched,
                unmatched_bus_count=unmatched,
                coverage_percent=round(coverage, 2),
                warnings=warnings,
                source_file_reference=source_file_reference,
                base_mva=case.sbase,
                buses=case.buses,
                branches=case.branches,
                transformers=case.transformers,
                loads=case.loads,
                generators=case.generators,
            )

        # LOAD_ONLY — validate against the Current TopologyVersion, if any.
        current_topology = self.repo.get_current_topology_version()
        matched = 0
        unmatched = 0
        if current_topology is not None:
            for load in case.loads:
                bus = self.repo.get_topology_bus_by_number(
                    current_topology.topology_version_id, load.bus_number
                )
                if bus is not None:
                    matched += 1
                else:
                    unmatched += 1
                    warnings.append(f"Load bus {load.bus_number} not found in Current topology.")
        else:
            unmatched = len(case.loads)
            warnings.append("No Current TopologyVersion exists to validate load buses against.")
        coverage = (matched / len(case.loads) * 100.0) if case.loads else 0.0
        return PreviewResultData(
            import_type="LOAD_ONLY",
            raw_version=case.rev,
            bus_count=len(case.buses),
            branch_count=len(case.branches),
            transformer_count=len(case.transformers),
            load_count=len(case.loads),
            generator_count=len(case.generators),
            computed_signature=None,
            topology_reused=False,
            matched_bus_count=matched,
            unmatched_bus_count=unmatched,
            coverage_percent=round(coverage, 2),
            warnings=warnings,
            source_file_reference=source_file_reference,
            base_mva=case.sbase,
            buses=case.buses,
            branches=case.branches,
            transformers=case.transformers,
            loads=case.loads,
            generators=case.generators,
        )

    # --- Commit (Workflow 1-5, §8.4-§8.8) — persists, never activates -----------
    def commit(
        self, file_content: str, source_file_reference: str, actor_user_id: uuid.UUID
    ) -> RawFileImportBatch:
        try:
            case = parse_raw(file_content)
        except RawParseError as exc:
            raise RawFileParseError(str(exc)) from exc

        if case.is_full_topology:
            batch = self._commit_full_topology(case, source_file_reference, actor_user_id)
        else:
            batch = self._commit_load_only(case, source_file_reference, actor_user_id)

        self._audit(
            entity_type="RawFileImportBatch",
            entity_id=str(batch.batch_id),
            event_type="created",
            actor_user_id=actor_user_id,
            change_reason=f"Committed {batch.import_type} import: {source_file_reference}",
        )
        return batch

    def _commit_full_topology(
        self, case: ParsedCase, source_file_reference: str, actor_user_id: uuid.UUID
    ) -> RawFileImportBatch:
        signature = compute_topology_signature(case.buses, case.branches, case.transformers)
        warnings: list[dict] = [
            {"category": _categorize_parser_warning(w), "message": w} for w in case.warnings
        ]

        existing_topology = self.repo.find_topology_version_by_signature(signature)
        is_new_topology = existing_topology is None

        batch = self.repo.add_batch(
            RawFileImportBatch(
                batch_id=uuid.uuid4(),
                source_file_reference=source_file_reference,
                imported_by_user_id=actor_user_id,
                import_type="FULL_TOPOLOGY_WITH_LOAD",
                computed_signature=signature,
                status="Parsing",
                warnings=[],
            )
        )

        if is_new_topology:
            topology_version = self.repo.add_topology_version(
                TopologyVersion(
                    topology_version_id=uuid.uuid4(),
                    signature=signature,
                    status="Imported",
                    created_from_batch_id=batch.batch_id,
                )
            )
            # Batch-inserted (Phase 4.1 stabilization): building the full
            # list of ORM objects first and adding them via `add_all()` +
            # one `flush()` per entity type turns what was previously one
            # database round trip per *row* into one per *type*, while
            # still populating each row's PK in place on the same objects
            # (read below via `.topology_bus_id`/etc.) before the next
            # entity type, which references those PKs, is built.
            bus_id_by_number: dict[int, int] = {}
            buses: list[TopologyBus] = []
            for parsed_bus in case.buses:
                substation_id = self._match_substation_for_bus(parsed_bus.bus_name)
                if substation_id is None:
                    warnings.append(
                        {
                            "category": "unmatched_bus",
                            "message": f"Bus {parsed_bus.bus_number} did not match any substation.",
                        }
                    )
                buses.append(
                    TopologyBus(
                        topology_version_id=topology_version.topology_version_id,
                        bus_number=parsed_bus.bus_number,
                        bus_name=parsed_bus.bus_name,
                        base_kv=parsed_bus.base_kv,
                        substation_id=substation_id,
                        psse_area=parsed_bus.area,
                        psse_zone=parsed_bus.zone,
                        psse_owner=parsed_bus.owner,
                    )
                )
            self.repo.add_topology_buses(buses)
            for bus in buses:
                bus_id_by_number[bus.bus_number] = bus.topology_bus_id

            branch_lookup: dict[tuple, int] = {}
            branches: list[TopologyBranch] = []
            branch_keys: list[tuple] = []
            for parsed_branch in case.branches:
                if (
                    parsed_branch.from_bus not in bus_id_by_number
                    or parsed_branch.to_bus not in bus_id_by_number
                ):
                    warnings.append(
                        {
                            "category": "unmatched_branch_reference",
                            "message": (
                                f"Branch {parsed_branch.from_bus}-{parsed_branch.to_bus} "
                                f"'{parsed_branch.ckt_id}' references an unknown bus."
                            ),
                        }
                    )
                    continue
                branches.append(
                    TopologyBranch(
                        topology_version_id=topology_version.topology_version_id,
                        from_bus_id=bus_id_by_number[parsed_branch.from_bus],
                        to_bus_id=bus_id_by_number[parsed_branch.to_bus],
                        ckt_id=parsed_branch.ckt_id,
                        r=parsed_branch.r,
                        x=parsed_branch.x,
                        b=parsed_branch.b,
                        rate_a=parsed_branch.rate_a,
                        rate_b=parsed_branch.rate_b,
                        rate_c=parsed_branch.rate_c,
                    )
                )
                branch_keys.append(
                    (parsed_branch.from_bus, parsed_branch.to_bus, parsed_branch.ckt_id)
                )
            self.repo.add_topology_branches(branches)
            for key, branch in zip(branch_keys, branches, strict=True):
                branch_lookup[key] = branch.topology_branch_id

            transformer_lookup: dict[tuple, int] = {}
            transformers: list[TopologyTransformer] = []
            transformer_keys: list[tuple] = []
            for parsed_transformer in case.transformers:
                if (
                    parsed_transformer.from_bus not in bus_id_by_number
                    or parsed_transformer.to_bus not in bus_id_by_number
                ):
                    warnings.append(
                        {
                            "category": "unmatched_transformer_reference",
                            "message": (
                                f"Transformer {parsed_transformer.from_bus}-"
                                f"{parsed_transformer.to_bus} '{parsed_transformer.ckt_id}' "
                                "references an unknown bus."
                            ),
                        }
                    )
                    continue
                tertiary_bus_id = None
                if parsed_transformer.tertiary_bus is not None:
                    tertiary_bus_id = bus_id_by_number.get(parsed_transformer.tertiary_bus)
                transformers.append(
                    TopologyTransformer(
                        topology_version_id=topology_version.topology_version_id,
                        from_bus_id=bus_id_by_number[parsed_transformer.from_bus],
                        to_bus_id=bus_id_by_number[parsed_transformer.to_bus],
                        tertiary_bus_id=tertiary_bus_id,
                        ckt_id=parsed_transformer.ckt_id,
                        r=parsed_transformer.r,
                        x=parsed_transformer.x,
                        rate_a=parsed_transformer.rate_a,
                    )
                )
                transformer_keys.append(
                    (
                        parsed_transformer.from_bus,
                        parsed_transformer.to_bus,
                        parsed_transformer.ckt_id,
                    )
                )
            self.repo.add_topology_transformers(transformers)
            for key, transformer in zip(transformer_keys, transformers, strict=True):
                transformer_lookup[key] = transformer.topology_transformer_id

            batch.topology_version_id = topology_version.topology_version_id
        else:
            # Reused topology — re-derive the PSS/E-bus-number-keyed lookups
            # from the already-persisted rows, so `case.branches`/
            # `case.transformers` (still keyed by PSS/E bus number, since
            # that is all the freshly-parsed file itself knows) can be
            # correlated against them for in-service state below.
            topology_version = existing_topology
            bus_id_by_number = {
                bus.bus_number: bus.topology_bus_id
                for bus in self.repo.list_topology_buses(topology_version.topology_version_id)
            }
            bus_number_by_id = {v: k for k, v in bus_id_by_number.items()}
            branch_lookup = {
                (
                    bus_number_by_id[branch.from_bus_id],
                    bus_number_by_id[branch.to_bus_id],
                    branch.ckt_id,
                ): (branch.topology_branch_id)
                for branch in self.repo.list_topology_branches(topology_version.topology_version_id)
            }
            transformer_lookup = {
                (
                    bus_number_by_id[t.from_bus_id],
                    bus_number_by_id[t.to_bus_id],
                    t.ckt_id,
                ): t.topology_transformer_id
                for t in self.repo.list_topology_transformers(topology_version.topology_version_id)
            }
            batch.topology_version_id = topology_version.topology_version_id

        load_snapshot = self._create_load_snapshot(
            case,
            topology_version.topology_version_id,
            batch.batch_id,
            bus_id_by_number,
            branch_lookup,
            transformer_lookup,
        )
        batch.load_snapshot_id = load_snapshot.load_snapshot_id

        if is_new_topology:
            self._run_matching(topology_version.topology_version_id, actor_user_id=None)

        batch.status = "CompletedWithWarnings" if warnings else "Completed"
        batch.warnings = warnings
        return batch

    def _commit_load_only(
        self, case: ParsedCase, source_file_reference: str, actor_user_id: uuid.UUID
    ) -> RawFileImportBatch:
        current_topology = self.repo.get_current_topology_version()
        if current_topology is None:
            raise NoCurrentTopologyVersionError()

        batch = self.repo.add_batch(
            RawFileImportBatch(
                batch_id=uuid.uuid4(),
                source_file_reference=source_file_reference,
                imported_by_user_id=actor_user_id,
                import_type="LOAD_ONLY",
                computed_signature=None,
                topology_version_id=current_topology.topology_version_id,
                status="Parsing",
                warnings=[],
            )
        )

        bus_id_by_number = {
            bus.bus_number: bus.topology_bus_id
            for bus in self.repo.list_topology_buses(current_topology.topology_version_id)
        }
        warnings: list[dict] = [
            {"category": _categorize_parser_warning(w), "message": w} for w in case.warnings
        ]
        matched_loads = [load for load in case.loads if load.bus_number in bus_id_by_number]
        for load in case.loads:
            if load.bus_number not in bus_id_by_number:
                warnings.append(
                    {
                        "category": "unmatched_load_bus",
                        "message": f"Load bus {load.bus_number} not found in Current topology.",
                    }
                )

        if case.loads and not matched_loads:
            batch.status = "Failed"
            batch.fatal_error = "Zero loads matched the Current TopologyVersion's buses."
            batch.warnings = warnings
            return batch

        load_snapshot = self.repo.add_load_snapshot(
            LoadSnapshot(
                load_snapshot_id=uuid.uuid4(),
                topology_version_id=current_topology.topology_version_id,
                created_from_batch_id=batch.batch_id,
                status="Imported",
            )
        )
        for load in matched_loads:
            self.repo.add_network_load(
                NetworkLoad(
                    load_snapshot_id=load_snapshot.load_snapshot_id,
                    topology_bus_id=bus_id_by_number[load.bus_number],
                    load_id=load.load_id,
                    p_mw=load.p_mw,
                    q_mvar=load.q_mvar,
                )
            )

        batch.load_snapshot_id = load_snapshot.load_snapshot_id
        batch.status = "CompletedWithWarnings" if warnings else "Completed"
        batch.warnings = warnings
        return batch

    def _create_load_snapshot(
        self,
        case: ParsedCase,
        topology_version_id: uuid.UUID,
        batch_id: uuid.UUID,
        bus_id_by_number: dict[int, int],
        branch_lookup: dict[tuple, int] | None = None,
        transformer_lookup: dict[tuple, int] | None = None,
    ) -> LoadSnapshot:
        branch_lookup = branch_lookup or {}
        transformer_lookup = transformer_lookup or {}
        load_snapshot = self.repo.add_load_snapshot(
            LoadSnapshot(
                load_snapshot_id=uuid.uuid4(),
                topology_version_id=topology_version_id,
                created_from_batch_id=batch_id,
                status="Imported",
            )
        )
        for parsed_bus in case.buses:
            topology_bus_id = bus_id_by_number.get(parsed_bus.bus_number)
            if topology_bus_id is None:
                continue
            self.repo.add_load_snapshot_bus_state(
                LoadSnapshotBusState(
                    load_snapshot_id=load_snapshot.load_snapshot_id,
                    topology_bus_id=topology_bus_id,
                    bus_type=parsed_bus.ide,
                    voltage_mag=parsed_bus.voltage_mag,
                    voltage_angle=parsed_bus.voltage_angle,
                    in_service=parsed_bus.ide != 4,
                )
            )
        for parsed_branch in case.branches:
            topology_branch_id = branch_lookup.get(
                (parsed_branch.from_bus, parsed_branch.to_bus, parsed_branch.ckt_id)
            )
            if topology_branch_id is None:
                continue
            self.repo.add_load_snapshot_element_state(
                LoadSnapshotElementState(
                    load_snapshot_id=load_snapshot.load_snapshot_id,
                    topology_branch_id=topology_branch_id,
                    in_service=parsed_branch.status,
                )
            )
        for parsed_transformer in case.transformers:
            topology_transformer_id = transformer_lookup.get(
                (parsed_transformer.from_bus, parsed_transformer.to_bus, parsed_transformer.ckt_id)
            )
            if topology_transformer_id is None:
                continue
            self.repo.add_load_snapshot_element_state(
                LoadSnapshotElementState(
                    load_snapshot_id=load_snapshot.load_snapshot_id,
                    topology_transformer_id=topology_transformer_id,
                    in_service=parsed_transformer.status,
                )
            )
        for load in case.loads:
            topology_bus_id = bus_id_by_number.get(load.bus_number)
            if topology_bus_id is None:
                continue
            self.repo.add_network_load(
                NetworkLoad(
                    load_snapshot_id=load_snapshot.load_snapshot_id,
                    topology_bus_id=topology_bus_id,
                    load_id=load.load_id,
                    p_mw=load.p_mw,
                    q_mvar=load.q_mvar,
                )
            )
        for generator in case.generators:
            topology_bus_id = bus_id_by_number.get(generator.bus_number)
            if topology_bus_id is None:
                continue
            self.repo.add_network_generator(
                NetworkGenerator(
                    load_snapshot_id=load_snapshot.load_snapshot_id,
                    topology_bus_id=topology_bus_id,
                    gen_id=generator.gen_id,
                    p_gen=generator.p_gen,
                    q_gen=generator.q_gen,
                    p_max=generator.p_max,
                    p_min=generator.p_min,
                    q_max=generator.q_max,
                    q_min=generator.q_min,
                )
            )
        return load_snapshot

    # --- Activate (Workflow 7, §8.10) --------------------------------------------
    def activate(
        self, batch_id: uuid.UUID, *, change_reason: str, actor_user_id: uuid.UUID
    ) -> RawFileImportBatch:
        batch = self.repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError(f"Import batch {batch_id} not found")
        if batch.status not in ("Completed", "CompletedWithWarnings"):
            raise BatchNotActivatableError(batch.status)

        now = datetime.now(UTC)
        new_topology = (
            self.repo.get_topology_version_by_id(batch.topology_version_id)
            if batch.topology_version_id
            else None
        )
        new_snapshot = (
            self.repo.get_load_snapshot_by_id(batch.load_snapshot_id)
            if batch.load_snapshot_id
            else None
        )

        topology_is_new = new_topology is not None and new_topology.status == "Imported"
        if topology_is_new:
            previous_current_topology = self.repo.get_current_topology_version()
            if previous_current_topology is not None:
                previous_current_topology.status = "Superseded"
                previous_current_topology.superseded_at = now
            new_topology.status = "Current"
            new_topology.promoted_at = now

        if new_snapshot is not None:
            previous_current_snapshot = self.repo.get_current_load_snapshot()
            if previous_current_snapshot is not None:
                previous_current_snapshot.status = "Superseded"
                previous_current_snapshot.superseded_at = now
            new_snapshot.status = "Current"
            new_snapshot.promoted_at = now

        self._audit(
            entity_type="RawFileImportBatch",
            entity_id=str(batch.batch_id),
            event_type="activated",
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return batch

    # --- Read interfaces -----------------------------------------------------
    def get_batch(self, batch_id: uuid.UUID) -> RawFileImportBatch:
        batch = self.repo.get_batch_by_id(batch_id)
        if batch is None:
            raise NotFoundError(f"Import batch {batch_id} not found")
        return batch

    def list_batches(
        self, *, page: int, page_size: int, status: str | None = None
    ) -> tuple[list[RawFileImportBatch], int]:
        return self.repo.list_batches(offset=(page - 1) * page_size, limit=page_size, status=status)

    def list_topology_versions(
        self, *, page: int, page_size: int
    ) -> tuple[list[TopologyVersion], int]:
        return self.repo.list_topology_versions(offset=(page - 1) * page_size, limit=page_size)

    def list_load_snapshots(
        self, *, page: int, page_size: int, topology_version_id: uuid.UUID | None = None
    ) -> tuple[list[LoadSnapshot], int]:
        return self.repo.list_load_snapshots(
            offset=(page - 1) * page_size, limit=page_size, topology_version_id=topology_version_id
        )

    def get_current_status(self) -> tuple[TopologyVersion | None, LoadSnapshot | None]:
        return self.repo.get_current_topology_version(), self.repo.get_current_load_snapshot()

    def counts_for_topology_version(self, topology_version_id: uuid.UUID) -> tuple[int, int, int]:
        return (
            len(self.repo.list_topology_buses(topology_version_id)),
            len(self.repo.list_topology_branches(topology_version_id)),
            len(self.repo.list_topology_transformers(topology_version_id)),
        )

    def counts_for_load_snapshot(self, load_snapshot_id: uuid.UUID) -> tuple[int, int]:
        return (
            len(self.repo.list_network_loads(load_snapshot_id)),
            len(self.repo.list_network_generators(load_snapshot_id)),
        )

    # --- API-facing summary DTOs ----------------------------------------------
    def _batch_summary(self, batch: RawFileImportBatch) -> BatchSummary:
        imported_by = self._resolve_user(batch.imported_by_user_id)
        assert imported_by is not None
        return BatchSummary(
            batch_id=batch.batch_id,
            source_file_reference=batch.source_file_reference,
            imported_by=imported_by,
            import_type=batch.import_type,
            status=batch.status,
            computed_signature=batch.computed_signature,
            topology_version_id=batch.topology_version_id,
            load_snapshot_id=batch.load_snapshot_id,
            warnings=batch.warnings,
            fatal_error=batch.fatal_error,
            created_at=batch.created_at,
            finding_groups=_aggregate_findings(batch.warnings),
        )

    def _registry_matching_counts(
        self, batch: RawFileImportBatch, finding_groups: list[FindingGroup]
    ) -> tuple[int, int] | None:
        """Matched/unmatched counts for the Import Result page's Registry
        Matching section (§8.9d) — read from rows this batch's own commit
        already persisted (`list_topology_buses`/`list_network_loads`,
        the same repository methods `counts_for_topology_version`/
        `counts_for_load_snapshot` already use above), plus the
        already-computed `finding_groups` for the load-only case. No new
        parsing, no new engineering calculation — a count over
        already-loaded rows and already-aggregated findings."""
        if batch.import_type == "FULL_TOPOLOGY_WITH_LOAD":
            if batch.topology_version_id is None:
                return None
            buses = self.repo.list_topology_buses(batch.topology_version_id)
            if not buses:
                return None
            matched = sum(1 for bus in buses if bus.substation_id is not None)
            return matched, len(buses) - matched

        # LOAD_ONLY: matched loads are the ones actually persisted;
        # unmatched loads are never persisted, only recorded as findings.
        if batch.load_snapshot_id is None:
            return None
        matched = len(self.repo.list_network_loads(batch.load_snapshot_id))
        unmatched = sum(
            group.count for group in finding_groups if group.category == "unmatched_load_bus"
        )
        if matched == 0 and unmatched == 0:
            return None
        return matched, unmatched

    def get_batch_summary(self, batch_id: uuid.UUID) -> BatchSummary:
        batch = self.get_batch(batch_id)
        summary = self._batch_summary(batch)
        counts = self._registry_matching_counts(batch, summary.finding_groups)
        if counts is not None:
            matched, unmatched = counts
            total = matched + unmatched
            summary.matched_count = matched
            summary.unmatched_count = unmatched
            summary.coverage_percent = round((matched / total * 100.0) if total else 0.0, 2)
        return summary

    def list_batch_summaries(
        self, *, page: int, page_size: int, status: str | None = None
    ) -> tuple[list[BatchSummary], int]:
        items, total = self.list_batches(page=page, page_size=page_size, status=status)
        return [self._batch_summary(b) for b in items], total

    def _topology_version_summary(self, version: TopologyVersion) -> TopologyVersionSummary:
        bus_count, branch_count, transformer_count = self.counts_for_topology_version(
            version.topology_version_id
        )
        return TopologyVersionSummary(
            topology_version_id=version.topology_version_id,
            signature=version.signature,
            status=version.status,
            created_from_batch_id=version.created_from_batch_id,
            promoted_at=version.promoted_at,
            superseded_at=version.superseded_at,
            created_at=version.created_at,
            bus_count=bus_count,
            branch_count=branch_count,
            transformer_count=transformer_count,
        )

    def get_topology_version_summary(
        self, topology_version_id: uuid.UUID
    ) -> TopologyVersionSummary:
        version = self.repo.get_topology_version_by_id(topology_version_id)
        if version is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        return self._topology_version_summary(version)

    def list_topology_version_summaries(
        self, *, page: int, page_size: int
    ) -> tuple[list[TopologyVersionSummary], int]:
        items, total = self.list_topology_versions(page=page, page_size=page_size)
        return [self._topology_version_summary(v) for v in items], total

    def _load_snapshot_summary(self, snapshot: LoadSnapshot) -> LoadSnapshotSummary:
        load_count, generator_count = self.counts_for_load_snapshot(snapshot.load_snapshot_id)
        return LoadSnapshotSummary(
            load_snapshot_id=snapshot.load_snapshot_id,
            topology_version_id=snapshot.topology_version_id,
            status=snapshot.status,
            promoted_at=snapshot.promoted_at,
            superseded_at=snapshot.superseded_at,
            created_at=snapshot.created_at,
            load_count=load_count,
            generator_count=generator_count,
        )

    def get_load_snapshot_summary(self, load_snapshot_id: uuid.UUID) -> LoadSnapshotSummary:
        snapshot = self.repo.get_load_snapshot_by_id(load_snapshot_id)
        if snapshot is None:
            raise NotFoundError(f"LoadSnapshot {load_snapshot_id} not found")
        return self._load_snapshot_summary(snapshot)

    def list_load_snapshot_summaries(
        self, *, page: int, page_size: int, topology_version_id: uuid.UUID | None = None
    ) -> tuple[list[LoadSnapshotSummary], int]:
        items, total = self.list_load_snapshots(
            page=page, page_size=page_size, topology_version_id=topology_version_id
        )
        return [self._load_snapshot_summary(s) for s in items], total

    def get_current_status_summary(self) -> CurrentStatus:
        topology, snapshot = self.get_current_status()
        return CurrentStatus(
            current_topology_version=(
                self._topology_version_summary(topology) if topology else None
            ),
            current_load_snapshot=(self._load_snapshot_summary(snapshot) if snapshot else None),
        )

    # --- EquipmentTopologyMap (§8a) ------------------------------------------------
    def _run_matching(
        self, topology_version_id: uuid.UUID, *, actor_user_id: uuid.UUID | None
    ) -> None:
        """(Re)computes `EquipmentTopologyMap` entries for every eligible
        `CircuitTerminal` against one `TopologyVersion`'s structural data —
        excluding `ENTERED_IN_ERROR` records (§8a.7, §9 rule 15). Never
        writes to Equipment Registry (§8a.6, §9 rule 14)."""
        terminals = self.repo.list_active_circuit_terminals()
        if not terminals:
            return

        # Resolve each terminal's substation via its voltage yard.
        terminal_candidates: list[TerminalCandidate] = []
        circuits_by_id: dict[uuid.UUID, Circuit] = {}
        for terminal in terminals:
            circuit = circuits_by_id.get(terminal.circuit_id)
            if circuit is None:
                circuit = self.repo.get_circuit_by_id(terminal.circuit_id)
                if circuit is None:
                    continue
                circuits_by_id[terminal.circuit_id] = circuit
            substation_id = self._terminal_substation_id(terminal)
            if substation_id is None:
                continue
            terminal_candidates.append(
                TerminalCandidate(
                    circuit_terminal_id=terminal.circuit_terminal_id,
                    circuit_id=terminal.circuit_id,
                    bay_number=circuit.bay_number,
                    substation_id=substation_id,
                )
            )

        buses = self.repo.list_topology_buses(topology_version_id)
        bus_substation_by_id = {bus.topology_bus_id: bus.substation_id for bus in buses}

        elements: list[TopologyElementCandidate] = []
        for branch in self.repo.list_topology_branches(topology_version_id):
            elements.append(
                TopologyElementCandidate(
                    element_type="branch",
                    element_id=branch.topology_branch_id,
                    from_substation_id=bus_substation_by_id.get(branch.from_bus_id),
                    to_substation_id=bus_substation_by_id.get(branch.to_bus_id),
                    ckt_id=branch.ckt_id,
                )
            )
        for transformer in self.repo.list_topology_transformers(topology_version_id):
            elements.append(
                TopologyElementCandidate(
                    element_type="transformer",
                    element_id=transformer.topology_transformer_id,
                    from_substation_id=bus_substation_by_id.get(transformer.from_bus_id),
                    to_substation_id=bus_substation_by_id.get(transformer.to_bus_id),
                    ckt_id=transformer.ckt_id,
                )
            )

        results = compute_matches(terminal_candidates, elements)
        for result in results:
            existing_entry = self.repo.get_map_entry(
                topology_version_id, result.circuit_terminal_id
            )
            if existing_entry is None:
                self.repo.add_map_entry(
                    EquipmentTopologyMap(
                        map_id=uuid.uuid4(),
                        topology_version_id=topology_version_id,
                        circuit_terminal_id=result.circuit_terminal_id,
                        topology_branch_id=result.topology_branch_id,
                        topology_transformer_id=result.topology_transformer_id,
                        match_outcome=result.match_outcome,
                    )
                )
            else:
                existing_entry.topology_branch_id = result.topology_branch_id
                existing_entry.topology_transformer_id = result.topology_transformer_id
                existing_entry.match_outcome = result.match_outcome
                existing_entry.discrepancy_resolution = None
                existing_entry.resolved_by_user_id = None
                existing_entry.resolved_at = None
            self._audit(
                entity_type="EquipmentTopologyMap",
                entity_id=f"{topology_version_id}:{result.circuit_terminal_id}",
                event_type="equipment_match_computed",
                actor_user_id=actor_user_id,
                change_reason=f"Match outcome: {result.match_outcome}",
            )

    def _terminal_substation_id(self, terminal: CircuitTerminal) -> uuid.UUID | None:
        """`CircuitTerminal.voltage_yard_id` resolves to `SubstationVoltageYard`
        — one join away from the terminal's own substation (ADR-008)."""
        yard = self.db.get(SubstationVoltageYard, terminal.voltage_yard_id)
        return yard.substation_id if yard is not None else None

    def recompute_matching(self, topology_version_id: uuid.UUID, actor_user_id: uuid.UUID) -> None:
        """Explicit, on-demand recomputation — callable any time Equipment
        Registry's own data changes, independent of a new import
        (psse-integration-module.md §8a domain-model note)."""
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        self._run_matching(topology_version_id, actor_user_id=actor_user_id)

    def list_map_entries(
        self,
        *,
        topology_version_id: uuid.UUID,
        page: int,
        page_size: int,
        match_outcome: str | None = None,
    ) -> tuple[list[EquipmentTopologyMap], int]:
        return self.repo.list_map_entries(
            topology_version_id=topology_version_id,
            offset=(page - 1) * page_size,
            limit=page_size,
            match_outcome=match_outcome,
        )

    def resolve_discrepancy(
        self,
        map_id: uuid.UUID,
        *,
        resolution: str,
        change_reason: str,
        actor_user_id: uuid.UUID,
    ) -> EquipmentTopologyMapEntry:
        """Records the engineer's classification decision on this
        module's own `EquipmentTopologyMap` row. **Never writes to
        Equipment Registry** — an "accepted" discrepancy means the engineer
        has confirmed the network genuinely changed and will separately
        correct Equipment Registry through its own service layer/UI if
        warranted; this method only closes the review item on this side
        (psse-integration-module.md §8a.5, §8a.6)."""
        entry = self.repo.get_map_entry_by_id(map_id)
        if entry is None:
            raise NotFoundError(f"EquipmentTopologyMap entry {map_id} not found")
        if entry.discrepancy_resolution is not None:
            raise DiscrepancyAlreadyResolvedError()

        entry.discrepancy_resolution = resolution
        entry.resolved_by_user_id = actor_user_id
        entry.resolved_at = datetime.now(UTC)
        self._audit(
            entity_type="EquipmentTopologyMap",
            entity_id=str(map_id),
            event_type="equipment_discrepancy_resolved",
            actor_user_id=actor_user_id,
            change_reason=change_reason,
        )
        return self._map_entry_summary(entry)

    def get_circuit_correlation(
        self, circuit_id: uuid.UUID, topology_version_id: uuid.UUID
    ) -> CircuitCorrelation:
        """Union-of-terminals resolution (ADR-007 §6, §10) — the interface
        a future Network Model would call to translate a scheme's `Circuit`
        reference into native PSS/E elements. Network Model itself is out
        of this phase's scope; this method only exposes the read
        interface psse-integration-module.md §13 specifies."""
        if self.repo.get_circuit_by_id(circuit_id) is None:
            raise NotFoundError(f"Circuit {circuit_id} not found")
        entries = self.repo.list_map_entries_for_circuit(topology_version_id, circuit_id)
        terminal_summaries = [self._map_entry_summary(entry) for entry in entries]
        all_terminals = self.repo.list_circuit_terminals_for_circuit(circuit_id)
        fully_resolved = len(entries) == len(all_terminals) and all(
            e.match_outcome == "clean_match" for e in entries
        )
        return CircuitCorrelation(
            circuit_id=circuit_id,
            topology_version_id=topology_version_id,
            terminals=terminal_summaries,
            fully_resolved=fully_resolved,
        )

    def _map_entry_summary(self, entry: EquipmentTopologyMap) -> EquipmentTopologyMapEntry:
        terminal = self.repo.get_circuit_terminal_by_id(entry.circuit_terminal_id)
        circuit = self.repo.get_circuit_by_id(terminal.circuit_id) if terminal else None
        substation_id = self._terminal_substation_id(terminal) if terminal else None
        substation_mnemonic = ""
        if substation_id is not None:
            substation_row = self.db.get(Substation, substation_id)
            substation_mnemonic = substation_row.mnemonic if substation_row else ""
        return EquipmentTopologyMapEntry(
            map_id=entry.map_id,
            topology_version_id=entry.topology_version_id,
            circuit_terminal_id=entry.circuit_terminal_id,
            circuit_id=circuit.circuit_id if circuit else uuid.UUID(int=0),
            circuit_bay_number=circuit.bay_number if circuit else "",
            substation_mnemonic=substation_mnemonic,
            topology_branch_id=entry.topology_branch_id,
            topology_transformer_id=entry.topology_transformer_id,
            match_outcome=entry.match_outcome,
            discrepancy_resolution=entry.discrepancy_resolution,
            resolved_by=self._resolve_user(entry.resolved_by_user_id),
            resolved_at=entry.resolved_at,
            created_at=entry.created_at,
        )

    def list_map_entry_summaries(
        self,
        *,
        topology_version_id: uuid.UUID,
        page: int,
        page_size: int,
        match_outcome: str | None = None,
    ) -> tuple[list[EquipmentTopologyMapEntry], int]:
        entries, total = self.list_map_entries(
            topology_version_id=topology_version_id,
            page=page,
            page_size=page_size,
            match_outcome=match_outcome,
        )
        return [self._map_entry_summary(entry) for entry in entries], total
