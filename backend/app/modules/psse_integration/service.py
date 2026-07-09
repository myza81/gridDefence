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
from types import SimpleNamespace

from sqlalchemy.orm import Session

from app.modules.equipment_registry.models import Circuit, CircuitTerminal, SubstationVoltageYard
from app.modules.iam.schemas import UserSummary
from app.modules.iam.service import IAMService
from app.modules.psse_integration.bus_classification import classify_bus_name
from app.modules.psse_integration.correlated_operational_model import (
    CorrelationStatus,
    bus_correlation_status,
    equipment_correlation_status,
)
from app.modules.psse_integration.exceptions import (
    BatchNotActivatableError,
    DiscrepancyAlreadyResolvedError,
    NoCurrentTopologyVersionError,
    NotFoundError,
    RawFileParseError,
)
from app.modules.psse_integration.load_sync_validation import (
    ActiveTopologyBusRef,
    LoadSyncValidationResult,
    validate_load_only_synchronization,
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
    BusCorrelationRefreshSummary,
    BusIdentityMismatchRow,
    CircuitCorrelation,
    CurrentStatus,
    EquipmentTopologyMapEntry,
    FindingGroup,
    LoadSnapshotSummary,
    LoadSyncValidationSummary,
    OperationalBranchView,
    OperationalBusView,
    OperationalLoadView,
    OperationalTransformerView,
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
    "missing_topology_load_bus": "engineering_review_required",
    "load_bus_identity_mismatch": "engineering_review_required",
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
    if category == "missing_topology_load_bus":
        noun = "bus" if count == 1 else "buses"
        return (
            f"{count} {noun} previously had load in the current network topology but "
            "are absent from this file."
        )
    if category == "load_bus_identity_mismatch":
        noun = "bus" if count == 1 else "buses"
        return (
            f"{count} {noun} matched by Bus Number but reported a different Bus Name "
            "or nominal voltage than the current network topology."
        )
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
        frequency_hz: float | None,
        case_description: str | None,
        raw_created: str | None,
        sync_validation: LoadSyncValidationSummary | None = None,
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
        self.frequency_hz = frequency_hz
        self.case_description = case_description
        self.raw_created = raw_created
        self.sync_validation = sync_validation


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

    def _match_substation_for_bus(self, bus_name: str | None) -> Substation | None:
        """Best-effort bus-to-substation matching by mnemonic prefix
        (psse-integration-module.md §9 rule 12's "unmatched buses are
        warnings only" — this module never invents or auto-creates a
        Substation Registry record; an unmatched bus simply has no
        `substation_id`). Substation mnemonics in this project are 4
        characters (e.g. `PKLG`, `IGBK`); real PSS/E bus names commonly
        embed the mnemonic plus a voltage/suffix (`PKLG132`, `SDAOFIC`) —
        matching the leading 4 characters is a deliberately simple,
        transparent heuristic, not a claim of perfect fidelity.

        Returns the full `Substation` row (not just its id) — Phase 7C's
        Correlated Operational Model and Preview enrichment both need the
        mnemonic for display, not only the id; callers that only need the
        id (e.g. `TopologyBus.substation_id`) read `.substation_id` off the
        result."""
        if not bus_name or len(bus_name.strip()) < 4:
            return None
        candidate_mnemonic = bus_name.strip()[:4]
        return self.repo.find_substation_by_mnemonic_ci(candidate_mnemonic)

    def _build_voltage_yard_lookup(
        self, substation_ids: list[uuid.UUID]
    ) -> dict[tuple[uuid.UUID, float], uuid.UUID]:
        """Phase 7C — "correlated Switchyard" resolution: matches a Bus's
        own `base_kv` against `SubstationVoltageYard`'s voltage level (via
        `VoltageLevel.nominal_kv`), for every Substation in
        `substation_ids`, in exactly two bulk queries regardless of how
        many Buses are being resolved (never one query per Bus)."""
        distinct_ids = list({sid for sid in substation_ids if sid is not None})
        yards = self.repo.list_voltage_yards_by_substation_ids(distinct_ids)
        if not yards:
            return {}
        nominal_kv_by_level_id = {
            vl.voltage_level_id: vl.nominal_kv for vl in self.repo.list_voltage_levels()
        }
        return {
            (yard.substation_id, float(nominal_kv_by_level_id[yard.voltage_level_id])): (
                yard.voltage_yard_id
            )
            for yard in yards
            if yard.voltage_level_id in nominal_kv_by_level_id
        }

    def _enrich_buses_for_preview(
        self, buses: list, bus_substations: list[Substation | None]
    ) -> list[SimpleNamespace]:
        """Phase 7C — Preview/Inspector enrichment (zero persistence): the
        same Substation match Preview's own Registry Matching count
        already computes (`_match_substation_for_bus`), now also exposed
        per-Bus with the shared Correlated Operational Model vocabulary,
        plus the "correlated Switchyard" resolution. Returns
        `SimpleNamespace` objects (not `ParsedBus` instances) — attribute-
        accessible like a real `ParsedBus` (for existing callers that read
        `result.buses[i].bus_number` directly off `preview()`'s own return
        value, and for Pydantic's `from_attributes=True`), while keeping
        `raw_parser.py` itself free of any dependency on Engineering
        Registry correlation; only this service-layer enrichment step
        carries that dependency (mirrors the same separation
        `bus_classification.py`'s own docstring already establishes for
        classification vs. correlation)."""
        voltage_yard_lookup = self._build_voltage_yard_lookup(
            [s.substation_id for s in bus_substations if s is not None]
        )
        enriched: list[SimpleNamespace] = []
        for bus, substation in zip(buses, bus_substations, strict=True):
            substation_id = substation.substation_id if substation is not None else None
            voltage_yard_id = (
                voltage_yard_lookup.get((substation_id, bus.base_kv))
                if substation_id is not None
                else None
            )
            enriched.append(
                SimpleNamespace(
                    bus_number=bus.bus_number,
                    bus_name=bus.bus_name,
                    base_kv=bus.base_kv,
                    ide=bus.ide,
                    area=bus.area,
                    zone=bus.zone,
                    owner=bus.owner,
                    voltage_mag=bus.voltage_mag,
                    voltage_angle=bus.voltage_angle,
                    bus_classification=bus.bus_classification,
                    in_service=bus.in_service,
                    substation_id=substation_id,
                    substation_mnemonic=(substation.mnemonic if substation is not None else None),
                    voltage_yard_id=voltage_yard_id,
                    correlation_status=bus_correlation_status(
                        bus.bus_classification, substation_id
                    ),
                )
            )
        return enriched

    # --- Load-only Snapshot Synchronisation validation (Phase 7B) ---------------
    def _validate_load_only_sync(
        self, case: ParsedCase, current_topology: TopologyVersion
    ) -> LoadSyncValidationResult:
        """Compares a load-only case's loads against the active topology's
        own bus records, correlated exclusively by Bus Number (EDR-007
        Engineering Principle 12). Read-only — never creates, updates, or
        infers `TopologyVersion`/`TopologyBus` rows."""
        topology_buses = self.repo.list_topology_buses(current_topology.topology_version_id)
        active_topology_buses = [
            ActiveTopologyBusRef(
                bus_number=bus.bus_number, bus_name=bus.bus_name, base_kv=bus.base_kv
            )
            for bus in topology_buses
        ]
        bus_number_by_id = {bus.topology_bus_id: bus.bus_number for bus in topology_buses}

        # "Active topology bus missing from load-only RAW" (requirement 2)
        # is answered against the topology's own previously Current
        # LoadSnapshot — the only reliable, already-known signal for "this
        # bus was expected to have load," since a topology bus is not
        # required to carry load at all (e.g. a generator or switching
        # bus); every other candidate signal would be a guess.
        previously_loaded_bus_numbers: set[int] = set()
        previous_snapshot = self.repo.get_current_load_snapshot()
        if (
            previous_snapshot is not None
            and previous_snapshot.topology_version_id == current_topology.topology_version_id
        ):
            previously_loaded_bus_numbers = {
                bus_number_by_id[load.topology_bus_id]
                for load in self.repo.list_network_loads(previous_snapshot.load_snapshot_id)
                if load.topology_bus_id in bus_number_by_id
            }

        incoming_bus_references = [
            ActiveTopologyBusRef(
                bus_number=bus.bus_number, bus_name=bus.bus_name, base_kv=bus.base_kv
            )
            for bus in case.buses
        ]

        return validate_load_only_synchronization(
            load_bus_numbers=[load.bus_number for load in case.loads],
            active_topology_buses=active_topology_buses,
            previously_loaded_bus_numbers=previously_loaded_bus_numbers,
            incoming_bus_references=incoming_bus_references,
        )

    def _sync_validation_summary(
        self, result: LoadSyncValidationResult
    ) -> LoadSyncValidationSummary:
        return LoadSyncValidationSummary(
            total_load_records=result.total_load_records,
            total_distinct_load_buses=result.total_distinct_load_buses,
            matched_load_buses=result.matched_load_buses,
            unmatched_load_buses=len(result.unmatched_load_bus_numbers),
            missing_topology_buses=len(result.missing_topology_bus_numbers),
            identity_mismatch_buses=len(result.identity_mismatches),
            unmatched_load_bus_numbers=result.unmatched_load_bus_numbers,
            missing_topology_bus_numbers=result.missing_topology_bus_numbers,
            identity_mismatches=[
                BusIdentityMismatchRow(
                    bus_number=mismatch.bus_number,
                    active_bus_name=mismatch.active_bus_name,
                    incoming_bus_name=mismatch.incoming_bus_name,
                    active_base_kv=mismatch.active_base_kv,
                    incoming_base_kv=mismatch.incoming_base_kv,
                    mismatch_reason=mismatch.mismatch_reason,
                )
                for mismatch in result.identity_mismatches
            ],
        )

    def _sync_validation_findings(self, result: LoadSyncValidationResult) -> list[tuple[str, str]]:
        """(category, message) pairs for `missing_topology_load_bus`/
        `load_bus_identity_mismatch` — mirrors the existing
        `unmatched_load_bus` warning text style exactly, so both flow
        through the same `_aggregate_findings`/finding-group pipeline."""
        findings: list[tuple[str, str]] = []
        for bus_number in result.missing_topology_bus_numbers:
            findings.append(
                (
                    "missing_topology_load_bus",
                    f"Bus {bus_number} previously had load in the current network topology "
                    "but is absent from this file.",
                )
            )
        for mismatch in result.identity_mismatches:
            findings.append(
                (
                    "load_bus_identity_mismatch",
                    f"Bus {mismatch.bus_number} identity mismatch: current topology reports "
                    f"name '{mismatch.active_bus_name}' at {mismatch.active_base_kv} kV; this "
                    f"file reports name '{mismatch.incoming_bus_name}' at "
                    f"{mismatch.incoming_base_kv} kV.",
                )
            )
        return findings

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
            bus_substations = [self._match_substation_for_bus(bus.bus_name) for bus in case.buses]
            matched = sum(1 for s in bus_substations if s is not None)
            unmatched = len(case.buses) - matched
            coverage = (matched / len(case.buses) * 100.0) if case.buses else 0.0
            enriched_buses = self._enrich_buses_for_preview(case.buses, bus_substations)
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
                buses=enriched_buses,
                branches=case.branches,
                transformers=case.transformers,
                loads=case.loads,
                generators=case.generators,
                frequency_hz=case.frequency_hz,
                case_description=case.case_description,
                raw_created=case.raw_created,
            )

        # LOAD_ONLY — validate against the Current TopologyVersion, if any.
        current_topology = self.repo.get_current_topology_version()
        matched = 0
        unmatched = 0
        sync_validation_summary: LoadSyncValidationSummary | None = None
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

            sync_result = self._validate_load_only_sync(case, current_topology)
            sync_validation_summary = self._sync_validation_summary(sync_result)
            warnings.extend(
                message for _category, message in self._sync_validation_findings(sync_result)
            )
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
            frequency_hz=case.frequency_hz,
            case_description=case.case_description,
            raw_created=case.raw_created,
            sync_validation=sync_validation_summary,
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
                substation = self._match_substation_for_bus(parsed_bus.bus_name)
                substation_id = substation.substation_id if substation is not None else None
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

        sync_result = self._validate_load_only_sync(case, current_topology)
        for category, message in self._sync_validation_findings(sync_result):
            warnings.append({"category": category, "message": message})

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
                    owner=load.owner,
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
                    owner=load.owner,
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

    # --- Correlated Operational Model (Phase 7C) --------------------------------
    #
    # Read-only query methods over already-persisted Operational Snapshot
    # (`psse_integration`) and Engineering Registry (Substation Registry /
    # Equipment Registry) data — never a new source of truth, never a
    # write path (operational-correlation-architecture.md §5, §9). These
    # are the intended, preferred engineering-consumption API for future
    # Defence Scheme modules, dashboards, and analytics — mirroring
    # `get_circuit_correlation`'s own, already-accepted shape, generalized
    # across every operational object type.

    _CORRELATION_STATUS_PRIORITY: dict[CorrelationStatus, int] = {
        "CORRELATED": 0,
        "ENGINEERING_REVIEW_REQUIRED": 1,
        "AMBIGUOUS": 2,
        "UNMATCHED_REGISTRY": 3,
        "UNMATCHED_OPERATIONAL": 4,
        "OUTSIDE_CURRENT_SCOPE": 5,
    }

    def refresh_bus_correlation(
        self, topology_version_id: uuid.UUID, actor_user_id: uuid.UUID
    ) -> BusCorrelationRefreshSummary:
        """Explicit, on-demand Bus -> Substation Registry correlation
        refresh (Phase 7D; UAT follow-up — `docs/testing/phase-7-uat-
        results.md` §10 remark on Test 10.4: Bus-to-Substation correlation
        is otherwise computed only once, at commit time, and does not
        automatically pick up a Substation created or corrected
        afterward). Mirrors `recompute_matching`'s own established pattern
        for `EquipmentTopologyMap` (psse-integration-module.md §8a) — an
        explicit, audited, callable-any-time recomputation, never
        automatic.

        Recomputes `TopologyBus.substation_id` via the same
        `_match_substation_for_bus` heuristic already used at commit time
        — introduces no new matching rule, no new engineering
        interpretation. Never creates, updates, or infers a Substation
        Registry record (`_match_substation_for_bus` only reads). Never
        touches RAW-derived topology facts (`bus_number`/`bus_name`/
        `base_kv`) or any other operational data — only the correlation
        link (`substation_id`) itself. "Correlated Switchyard"
        (`voltage_yard_id`) needs no separate refresh step: it is already
        computed at read time from `substation_id` + `base_kv`
        (`_build_voltage_yard_lookup`), never persisted, so it reflects
        the refreshed `substation_id` on the very next read."""
        topology_version = self.repo.get_topology_version_by_id(topology_version_id)
        if topology_version is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")

        buses = self.repo.list_topology_buses(topology_version_id)
        buses_correlated = 0
        buses_unmatched = 0
        buses_outside_scope = 0
        updated_count = 0

        for bus in buses:
            classification = classify_bus_name(bus.bus_name)
            substation = self._match_substation_for_bus(bus.bus_name)
            new_substation_id = substation.substation_id if substation is not None else None
            if new_substation_id != bus.substation_id:
                bus.substation_id = new_substation_id
                updated_count += 1

            status = bus_correlation_status(classification, new_substation_id)
            if status == "CORRELATED":
                buses_correlated += 1
            elif status == "OUTSIDE_CURRENT_SCOPE":
                buses_outside_scope += 1
            else:
                buses_unmatched += 1

        self._audit(
            entity_type="TopologyVersion",
            entity_id=str(topology_version_id),
            event_type="operational_correlation_refreshed",
            actor_user_id=actor_user_id,
            change_reason=(
                f"Bus correlation refresh: {updated_count} of {len(buses)} bus(es) updated "
                f"({buses_correlated} correlated, {buses_unmatched} unmatched, "
                f"{buses_outside_scope} outside current scope)"
            ),
        )

        return BusCorrelationRefreshSummary(
            topology_version_id=topology_version_id,
            buses_processed=len(buses),
            buses_correlated=buses_correlated,
            buses_unmatched=buses_unmatched,
            buses_outside_scope=buses_outside_scope,
            updated_count=updated_count,
        )

    def get_operational_bus_views(
        self, topology_version_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[OperationalBusView], int]:
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        buses = self.repo.list_topology_buses(topology_version_id)
        total = len(buses)
        offset = (page - 1) * page_size
        page_buses = buses[offset : offset + page_size]
        return self._build_operational_bus_views(topology_version_id, page_buses), total

    def get_operational_bus_view(
        self, topology_version_id: uuid.UUID, bus_number: int
    ) -> OperationalBusView:
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        bus = self.repo.get_topology_bus_by_number(topology_version_id, bus_number)
        if bus is None:
            raise NotFoundError(
                f"Bus {bus_number} not found in TopologyVersion {topology_version_id}"
            )
        return self._build_operational_bus_views(topology_version_id, [bus])[0]

    def _build_operational_bus_views(
        self, topology_version_id: uuid.UUID, buses: list[TopologyBus]
    ) -> list[OperationalBusView]:
        substation_ids = [b.substation_id for b in buses if b.substation_id is not None]
        substations_by_id = {
            s.substation_id: s for s in self.repo.list_substations_by_ids(substation_ids)
        }
        voltage_yard_lookup = self._build_voltage_yard_lookup(substation_ids)

        in_service_by_bus_id: dict[int, bool] = {}
        snapshot = self.repo.get_current_load_snapshot_for_topology(topology_version_id)
        if snapshot is not None:
            in_service_by_bus_id = {
                state.topology_bus_id: state.in_service
                for state in self.repo.list_load_snapshot_bus_states(snapshot.load_snapshot_id)
            }

        views: list[OperationalBusView] = []
        for bus in buses:
            classification = classify_bus_name(bus.bus_name)
            substation = (
                substations_by_id.get(bus.substation_id) if bus.substation_id is not None else None
            )
            voltage_yard_id = (
                voltage_yard_lookup.get((bus.substation_id, bus.base_kv))
                if bus.substation_id is not None
                else None
            )
            views.append(
                OperationalBusView(
                    topology_version_id=topology_version_id,
                    bus_number=bus.bus_number,
                    bus_name=bus.bus_name,
                    bus_classification=classification,
                    in_service=in_service_by_bus_id.get(bus.topology_bus_id),
                    substation_id=bus.substation_id,
                    substation_mnemonic=substation.mnemonic if substation is not None else None,
                    voltage_yard_id=voltage_yard_id,
                    correlation_status=bus_correlation_status(classification, bus.substation_id),
                )
            )
        return views

    def _element_correlation(
        self, map_entries: list[EquipmentTopologyMap]
    ) -> tuple[CorrelationStatus, EquipmentTopologyMap | None]:
        """Picks the "best" entry among possibly-multiple
        `EquipmentTopologyMap` rows referencing the same operational
        element (rare — e.g. both ends of a tee-off circuit discrepancy-
        matching the same element) and returns its correlation status. A
        deliberate simplification, documented rather than silently
        assumed away: not expected to arise in the ordinary single-
        circuit, two-terminal case."""
        if not map_entries:
            status = equipment_correlation_status(
                None, has_single_candidate=False, discrepancy_resolution=None
            )
            return status, None

        best_entry: EquipmentTopologyMap | None = None
        best_status: CorrelationStatus | None = None
        for entry in map_entries:
            has_single = (
                entry.topology_branch_id is not None or entry.topology_transformer_id is not None
            )
            status = equipment_correlation_status(
                entry.match_outcome,
                has_single_candidate=has_single,
                discrepancy_resolution=entry.discrepancy_resolution,
            )
            if best_status is None or (
                self._CORRELATION_STATUS_PRIORITY[status]
                < self._CORRELATION_STATUS_PRIORITY[best_status]
            ):
                best_status, best_entry = status, entry
        assert best_status is not None  # map_entries is non-empty here
        return best_status, best_entry

    def _resolve_circuit_context(
        self,
        entry: EquipmentTopologyMap | None,
        terminals_by_id: dict[uuid.UUID, CircuitTerminal],
        circuits_by_id: dict[uuid.UUID, Circuit],
    ) -> Circuit | None:
        if entry is None:
            return None
        terminal = terminals_by_id.get(entry.circuit_terminal_id)
        if terminal is None:
            return None
        return circuits_by_id.get(terminal.circuit_id)

    def _load_element_correlation_context(
        self, topology_version_id: uuid.UUID
    ) -> tuple[
        dict[int, list[EquipmentTopologyMap]],
        dict[int, list[EquipmentTopologyMap]],
        dict[uuid.UUID, CircuitTerminal],
        dict[uuid.UUID, Circuit],
    ]:
        """One bulk fetch of every `EquipmentTopologyMap` entry for this
        `TopologyVersion`, plus the `CircuitTerminal`/`Circuit` rows those
        entries reference — three queries total, shared by both
        `get_operational_branch_views` and `get_operational_transformer_views`,
        never one query per element (task's own "avoid N+1" requirement)."""
        entries = self.repo.list_all_map_entries(topology_version_id)
        entries_by_branch_id: dict[int, list[EquipmentTopologyMap]] = {}
        entries_by_transformer_id: dict[int, list[EquipmentTopologyMap]] = {}
        for entry in entries:
            if entry.topology_branch_id is not None:
                entries_by_branch_id.setdefault(entry.topology_branch_id, []).append(entry)
            if entry.topology_transformer_id is not None:
                entries_by_transformer_id.setdefault(entry.topology_transformer_id, []).append(
                    entry
                )

        circuit_terminal_ids = [e.circuit_terminal_id for e in entries]
        terminals_by_id = {
            t.circuit_terminal_id: t
            for t in self.repo.list_circuit_terminals_by_ids(circuit_terminal_ids)
        }
        circuit_ids = [t.circuit_id for t in terminals_by_id.values()]
        circuits_by_id = {c.circuit_id: c for c in self.repo.list_circuits_by_ids(circuit_ids)}
        return entries_by_branch_id, entries_by_transformer_id, terminals_by_id, circuits_by_id

    def _build_operational_branch_views(
        self, topology_version_id: uuid.UUID, branches: list[TopologyBranch]
    ) -> list[OperationalBranchView]:
        """Extracted from `get_operational_branch_views` (Phase 7F) so the
        same correlation logic can be reused for an arbitrary caller-supplied
        subset of branches — e.g. Network Model's path-verification
        traversal (`get_operational_branch_views_for_ids`) — without
        duplicating it. `get_operational_branch_views` itself is unchanged
        in behaviour; this is a pure extraction, not a new computation."""
        bus_number_by_id = {
            bus.topology_bus_id: bus.bus_number
            for bus in self.repo.list_topology_buses(topology_version_id)
        }
        entries_by_branch_id, _, terminals_by_id, circuits_by_id = (
            self._load_element_correlation_context(topology_version_id)
        )
        in_service_by_branch_id = self._element_in_service_map(
            topology_version_id, element_type="branch"
        )

        views = []
        for branch in branches:
            status, entry = self._element_correlation(
                entries_by_branch_id.get(branch.topology_branch_id, [])
            )
            circuit = self._resolve_circuit_context(entry, terminals_by_id, circuits_by_id)
            views.append(
                OperationalBranchView(
                    topology_version_id=topology_version_id,
                    topology_branch_id=branch.topology_branch_id,
                    from_bus_number=bus_number_by_id.get(branch.from_bus_id, 0),
                    to_bus_number=bus_number_by_id.get(branch.to_bus_id, 0),
                    ckt_id=branch.ckt_id,
                    in_service=in_service_by_branch_id.get(branch.topology_branch_id),
                    circuit_id=circuit.circuit_id if circuit is not None else None,
                    circuit_bay_number=circuit.bay_number if circuit is not None else None,
                    correlation_status=status,
                )
            )
        return views

    def get_operational_branch_views(
        self, topology_version_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[OperationalBranchView], int]:
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        branches = self.repo.list_topology_branches(topology_version_id)
        total = len(branches)
        offset = (page - 1) * page_size
        page_branches = branches[offset : offset + page_size]
        return self._build_operational_branch_views(topology_version_id, page_branches), total

    def get_operational_branch_views_for_ids(
        self, topology_version_id: uuid.UUID, topology_branch_ids: list[int]
    ) -> list[OperationalBranchView]:
        """Phase 7F — Operational Snapshot Verification Workspace. Same
        correlation logic as `get_operational_branch_views`, scoped to a
        caller-supplied set of Branch ids (e.g. Network Model's
        path-verification traversal's reached component) instead of a full
        paginated listing — avoids paginating through an entire topology
        version to look up a handful of branches, and never recomputes
        correlation a second way."""
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        if not topology_branch_ids:
            return []
        wanted = set(topology_branch_ids)
        branches = [
            b
            for b in self.repo.list_topology_branches(topology_version_id)
            if b.topology_branch_id in wanted
        ]
        return self._build_operational_branch_views(topology_version_id, branches)

    def _build_operational_transformer_views(
        self, topology_version_id: uuid.UUID, transformers: list[TopologyTransformer]
    ) -> list[OperationalTransformerView]:
        """Extracted from `get_operational_transformer_views` (Phase 7F) —
        see `_build_operational_branch_views`'s own docstring for the same
        rationale, applied here to Transformers."""
        bus_number_by_id = {
            bus.topology_bus_id: bus.bus_number
            for bus in self.repo.list_topology_buses(topology_version_id)
        }
        _, entries_by_transformer_id, terminals_by_id, circuits_by_id = (
            self._load_element_correlation_context(topology_version_id)
        )
        in_service_by_transformer_id = self._element_in_service_map(
            topology_version_id, element_type="transformer"
        )

        views = []
        for transformer in transformers:
            status, entry = self._element_correlation(
                entries_by_transformer_id.get(transformer.topology_transformer_id, [])
            )
            circuit = self._resolve_circuit_context(entry, terminals_by_id, circuits_by_id)
            views.append(
                OperationalTransformerView(
                    topology_version_id=topology_version_id,
                    topology_transformer_id=transformer.topology_transformer_id,
                    from_bus_number=bus_number_by_id.get(transformer.from_bus_id, 0),
                    to_bus_number=bus_number_by_id.get(transformer.to_bus_id, 0),
                    tertiary_bus_number=(
                        bus_number_by_id.get(transformer.tertiary_bus_id)
                        if transformer.tertiary_bus_id is not None
                        else None
                    ),
                    ckt_id=transformer.ckt_id,
                    in_service=in_service_by_transformer_id.get(
                        transformer.topology_transformer_id
                    ),
                    circuit_id=circuit.circuit_id if circuit is not None else None,
                    circuit_bay_number=circuit.bay_number if circuit is not None else None,
                    correlation_status=status,
                )
            )
        return views

    def get_operational_transformer_views(
        self, topology_version_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[OperationalTransformerView], int]:
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        transformers = self.repo.list_topology_transformers(topology_version_id)
        total = len(transformers)
        offset = (page - 1) * page_size
        page_transformers = transformers[offset : offset + page_size]
        return (
            self._build_operational_transformer_views(topology_version_id, page_transformers),
            total,
        )

    def get_operational_transformer_views_for_ids(
        self, topology_version_id: uuid.UUID, topology_transformer_ids: list[int]
    ) -> list[OperationalTransformerView]:
        """Phase 7F — mirrors `get_operational_branch_views_for_ids`, for
        Transformers."""
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        if not topology_transformer_ids:
            return []
        wanted = set(topology_transformer_ids)
        transformers = [
            t
            for t in self.repo.list_topology_transformers(topology_version_id)
            if t.topology_transformer_id in wanted
        ]
        return self._build_operational_transformer_views(topology_version_id, transformers)

    def get_operational_bus_views_for_numbers(
        self, topology_version_id: uuid.UUID, bus_numbers: list[int]
    ) -> list[OperationalBusView]:
        """Phase 7F — mirrors `get_operational_branch_views_for_ids`, for
        Buses: same correlation logic as `get_operational_bus_views`,
        scoped to a caller-supplied set of Bus Numbers (e.g. Network
        Model's path-verification traversal's reached set)."""
        if self.repo.get_topology_version_by_id(topology_version_id) is None:
            raise NotFoundError(f"TopologyVersion {topology_version_id} not found")
        if not bus_numbers:
            return []
        wanted = set(bus_numbers)
        buses = [
            b
            for b in self.repo.list_topology_buses(topology_version_id)
            if b.bus_number in wanted
        ]
        return self._build_operational_bus_views(topology_version_id, buses)

    def _element_in_service_map(
        self, topology_version_id: uuid.UUID, *, element_type: str
    ) -> dict[int, bool]:
        snapshot = self.repo.get_current_load_snapshot_for_topology(topology_version_id)
        if snapshot is None:
            return {}
        states = self.repo.list_load_snapshot_element_states(snapshot.load_snapshot_id)
        if element_type == "branch":
            return {
                state.topology_branch_id: state.in_service
                for state in states
                if state.topology_branch_id is not None
            }
        return {
            state.topology_transformer_id: state.in_service
            for state in states
            if state.topology_transformer_id is not None
        }

    def get_operational_load_views(
        self, load_snapshot_id: uuid.UUID, *, page: int, page_size: int
    ) -> tuple[list[OperationalLoadView], int]:
        """Collection-only (no singular getter) — `NetworkLoad` has no
        stable client-facing id beyond `(load_snapshot_id, bus_number,
        load_id)`, and Loads are consumed as a whole snapshot's worth, not
        looked up individually, per this phase's own scope."""
        snapshot = self.repo.get_load_snapshot_by_id(load_snapshot_id)
        if snapshot is None:
            raise NotFoundError(f"LoadSnapshot {load_snapshot_id} not found")
        loads = self.repo.list_network_loads(load_snapshot_id)
        total = len(loads)
        offset = (page - 1) * page_size
        page_loads = loads[offset : offset + page_size]

        topology_buses = self.repo.list_topology_buses(snapshot.topology_version_id)
        bus_by_id = {bus.topology_bus_id: bus for bus in topology_buses}
        substation_ids = [b.substation_id for b in topology_buses if b.substation_id is not None]
        substations_by_id = {
            s.substation_id: s for s in self.repo.list_substations_by_ids(substation_ids)
        }
        voltage_yard_lookup = self._build_voltage_yard_lookup(substation_ids)

        views = []
        for load in page_loads:
            bus = bus_by_id.get(load.topology_bus_id)
            substation = (
                substations_by_id.get(bus.substation_id)
                if bus is not None and bus.substation_id is not None
                else None
            )
            voltage_yard_id = (
                voltage_yard_lookup.get((bus.substation_id, bus.base_kv))
                if bus is not None and bus.substation_id is not None
                else None
            )
            views.append(
                OperationalLoadView(
                    load_snapshot_id=load.load_snapshot_id,
                    bus_number=bus.bus_number if bus is not None else 0,
                    load_id=load.load_id,
                    p_mw=load.p_mw,
                    q_mvar=load.q_mvar,
                    owner=load.owner,
                    load_category=None,
                    substation_id=bus.substation_id if bus is not None else None,
                    substation_mnemonic=substation.mnemonic if substation is not None else None,
                    voltage_yard_id=voltage_yard_id,
                    relevance_classification=None,
                    correlation_status="OUTSIDE_CURRENT_SCOPE",
                )
            )
        return views, total
