"""Continuous Evaluation Engine — synchronous core (CLAUDE.md §14;
continuous-evaluation-architecture.md; ADR-022; this sprint's own
instructions).

`ContinuousEvaluationService.evaluate(request)` is the one public
orchestration entry point: resolve the detectors applicable to the
request's scheme type (in deterministic registration order), run each one,
assemble their Findings into a single result. It contains **no MW-specific
calculation logic** — that lives entirely in `MwToleranceDetector`; the
engine never branches on a specific `detector_id` and never inspects a
Finding's own `evidence` shape.

**No persisted evaluation projection is implemented this sprint.**
continuous-evaluation-architecture.md §3 names four independent,
non-substitutable mechanisms: (1) event-driven background recalculation
(ADR-023, explicitly out of scope), (2) on-demand synchronous evaluation
(this sprint), (3) mandatory fresh evaluation at Publish (a future scheme
module's own concern), and (4) disposable cached projections — framed as
a *performance* optimisation for avoiding redundant recomputation. Nothing
in this sprint has a documented performance problem to justify that
optimisation (CLAUDE.md §21: avoid premature optimisation; base it on
measured evidence), and no real scheme module yet exists to be the
consumer of a persisted "latest projection" lookup. `evaluate()` therefore
returns a purely transient `EvaluationResult` — no `models.py`, no
Alembic migration, no database table in this sprint.

**No API/router is implemented this sprint.** continuous-evaluation-
architecture.md documents no HTTP contract of its own for this engine
(unlike, e.g., `findings_publication_governance`'s explicit "API Contract
(Concept)" section) — the engine is described as a shared, in-process
capability future scheme modules call from their own routers, not one
that exposes a standalone endpoint. `evaluate()` is therefore
FastAPI-independent by construction (plain constructor args, no
`Depends`), callable directly from tests, a future scheme service, or a
future background-refresh job using the same code path.

**Detector failure semantics (§11):** if any detector's own `detect()`
call raises, the whole evaluation fails — wrapped in
`DetectorExecutionFailedError` — rather than silently omitting that
detector's findings or returning a result that looks complete. The
architecture does not define a partial-evaluation mode, and reporting an
incomplete evaluation as though it were complete would be the less safe
choice for engineering governance.

────────────────────────────────────────────────────────────────────────
Sprint 6 — background refresh, disposable Evaluation Projection, and
platform-event consumption (ADR-023; continuous-evaluation-architecture.md
§3.1, §16).
────────────────────────────────────────────────────────────────────────

Three new public entry points, none of which duplicates detector
calculation logic — every one of them ultimately calls this same
`evaluate()`, via `run_refresh_worker_cycle`, exactly once per refresh:

- `notify_source_data_changed(event)` — ADR-023's own named entry point.
  Resolves affected `EvaluationTarget`s via the injected
  `AffectedSchemeResolver` (empty by default this sprint — no real
  source-to-scheme mapping exists yet) and calls `request_refresh` for
  each, deduplicated.
- `request_refresh(target, trigger, correlation_id)` — marks/creates the
  projection `STALE`, increments its `generation`, and enqueues an
  idempotent full-recompute job via the shared `ExecutionEngine`
  abstraction — never evaluates inline.
- `run_refresh_worker_cycle(target, requested_generation, trigger,
  correlation_id)` — the background worker's own entry point
  (`worker.py`). Claims the projection (`STALE`/`FAILED` -> `RECALCULATING`,
  visible immediately via its own commit), builds an `EvaluationRequest`
  through the registered `EvaluationRequestProvider`, calls this same
  `evaluate()`, and freezes the result into the projection.

**Coalescing / concurrency (this sprint's own instructions §15-16).**
At most one job is ever in flight per target: `request_refresh` only
enqueues when no job is already outstanding for that target — i.e. the
projection is neither already `RECALCULATING` (a worker is actively
running) nor already `STALE` (a job for this exact target is already
queued or about to be, since every transition to `STALE` in this method
always attempts an enqueue in the same call). A duplicate or overlapping
request while either is true just bumps `generation` and returns without
enqueueing, trusting the already-outstanding job to read the latest state
when it runs. For a job already `RECALCULATING`, "read the latest state"
happens at its own end-of-run check, which compares the generation the
worker started with (`requested_generation`) against the row's generation
at write time: equal -> safe to mark `CURRENT`; different -> a newer
invalidation arrived mid-run, so the worker leaves the projection `STALE`
and enqueues exactly one more job itself, closing the loop. This is the
entire mechanism that guarantees "no false CURRENT state if newer
invalidation occurred mid-run" — no timestamp comparison, no distributed
lock, only a per-target monotonic counter compared inside one row-locked
transaction.

**Outbox problem — resolved without a transactional outbox (this
sprint's own instructions §23).** Neither ADR-023 nor platform-event-
architecture.md defines a transactional-outbox mitigation, and none is
implemented here — instead, `request_refresh`/`notify_source_data_changed`
flush the projection mutation (no commit — this runs inside whatever
transaction the caller owns) and register the actual job submission on
`self.db`'s own `after_commit` event, firing exactly once, only if that
commit actually succeeds. A caller transaction that rolls back therefore
never enqueues a job at all — there is no dual-write gap to disclose.
This same mechanism is also what avoids a genuine deadlock under
`execution_mode="direct"` against a real multi-connection database (see
`request_refresh`'s own docstring for the full explanation) —
`run_refresh_worker_cycle`'s own "no projection found" no-op remains as a
defensive guard, not because this gap is expected in normal operation.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import event as sa_event
from sqlalchemy.orm import Session

from app.core.execution import ExecutionEngine, get_execution_engine
from app.modules.continuous_evaluation.detectors.registration import build_default_registry
from app.modules.continuous_evaluation.detectors.registry import DetectorRegistry
from app.modules.continuous_evaluation.exceptions import (
    DetectorExecutionFailedError,
    DetectorSourceMismatchError,
    NoApplicableDetectorsError,
    NoEvaluationRequestProviderError,
)
from app.modules.continuous_evaluation.models import EvaluationProjection
from app.modules.continuous_evaluation.provider import (
    EvaluationRequestProviderRegistry,
    build_default_provider_registry,
)
from app.modules.continuous_evaluation.repository import EvaluationProjectionRepository
from app.modules.continuous_evaluation.resolver import (
    AffectedSchemeResolver,
    NullAffectedSchemeResolver,
)
from app.modules.continuous_evaluation.schemas import (
    ChangeDescriptor,
    DetectorExecutionSummary,
    EvaluationRequest,
    EvaluationResult,
    EvaluationTarget,
    ProjectionDetail,
    ProjectionStatus,
    RefreshRequestResult,
)
from app.modules.engineering_parameters.service import EngineeringParameterService
from app.modules.findings_publication_governance.findings import Finding, SchemeType


class ContinuousEvaluationService:
    def __init__(
        self,
        db: Session,
        *,
        registry: DetectorRegistry | None = None,
        provider_registry: EvaluationRequestProviderRegistry | None = None,
        resolver: AffectedSchemeResolver | None = None,
        execution_engine: ExecutionEngine | None = None,
    ) -> None:
        """`registry` is an injectable override, defaulting to the
        application's own composed registry (`build_default_registry`) —
        used by this module's own engine tests to exercise multi-detector
        orchestration with stub detectors, independent of the MW
        detector's own calculation logic. Production callers never pass
        it; detector registration remains composition-only (this sprint's
        own instructions §20).

        `provider_registry`/`resolver`/`execution_engine` are the same
        kind of test-only injection seam, added this sprint: no real
        `EvaluationRequestProvider` or `AffectedSchemeResolver`
        implementation exists yet (no real scheme module), so the
        production defaults are, respectively, an empty registry and a
        resolver that always returns zero targets — both safe no-ops
        until a future scheme module registers itself."""
        self.db = db
        self.engineering_parameters = EngineeringParameterService(db)
        self.registry = registry or build_default_registry(self.engineering_parameters)
        self.provider_registry = provider_registry or build_default_provider_registry()
        self.resolver = resolver or NullAffectedSchemeResolver()
        self.execution_engine = execution_engine or get_execution_engine()
        self.projection_repo = EvaluationProjectionRepository(db)

    def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        detectors = self.registry.for_scheme_type(request.scheme_type)
        if not detectors:
            raise NoApplicableDetectorsError(request.scheme_type)

        all_findings: list[Finding] = []
        summaries: list[DetectorExecutionSummary] = []

        for detector in detectors:
            try:
                findings = detector.detect(request)
            except Exception as exc:  # noqa: BLE001 - re-raised as a domain error below
                raise DetectorExecutionFailedError(detector.detector_id, exc) from exc

            for finding in findings:
                if finding.source != detector.detector_id:
                    raise DetectorSourceMismatchError(detector.detector_id, finding.source)

            summaries.append(
                DetectorExecutionSummary(
                    detector_id=detector.detector_id, finding_count=len(findings)
                )
            )
            all_findings.extend(findings)

        return EvaluationResult(
            scheme_type=request.scheme_type,
            scheme_version_id=request.scheme_version_id,
            evaluation_snapshot_id=request.evaluation_snapshot_id,
            topology_version_id=request.topology_version_id,
            load_snapshot_id=request.load_snapshot_id,
            evaluated_at=datetime.now(UTC),
            detector_summaries=summaries,
            findings=all_findings,
        )

    # --- Sprint 6: platform-event consumption, refresh, and projection ---------

    def notify_source_data_changed(self, event: ChangeDescriptor) -> list[RefreshRequestResult]:
        """ADR-023's own named entry point. Never runs detector
        calculations directly (this sprint's own instructions §12) —
        only resolves affected targets and delegates to `request_refresh`,
        deduplicated and in deterministic (resolver-returned) order."""
        targets = self.resolver.resolve(event)
        deduplicated: list[EvaluationTarget] = []
        seen: set[tuple[SchemeType, uuid.UUID]] = set()
        for target in targets:
            key = (target.scheme_type, target.scheme_version_id)
            if key in seen:
                continue
            seen.add(key)
            deduplicated.append(target)

        return [
            self.request_refresh(
                target, trigger=event.descriptor, correlation_id=event.correlation_id
            )
            for target in deduplicated
        ]

    def request_refresh(
        self,
        target: EvaluationTarget,
        *,
        trigger: str,
        correlation_id: uuid.UUID | None = None,
    ) -> RefreshRequestResult:
        """Marks/creates the projection `STALE`, bumps its `generation`,
        and arranges an idempotent refresh job to be enqueued — never
        evaluates inline (this sprint's own instructions §17). Flush-only,
        no commit: this runs inside whatever transaction the caller owns
        (ADR-023 — "the same service-layer transaction boundary as the
        source module's own write"). See this module's own docstring for
        the full coalescing/concurrency algorithm.

        **The actual enqueue is deferred to `self.db`'s own
        `after_commit` event, not called synchronously here.** Found via
        this sprint's own PostgreSQL verification pass: `execution_mode=
        "direct"` (this platform's own documented, and default,
        deployment mode) runs the submitted job function immediately,
        in-process — including this module's own worker cycle, which
        opens a *separate* database connection (`worker.py`'s own
        `SessionLocal()`, mimicking a real separate worker process).
        Enqueueing synchronously, before this method's own mutation is
        committed, would have that separate connection block waiting to
        lock a row this connection's own uncommitted transaction still
        holds — a genuine self-deadlock on any real multi-connection
        database (invisible on SQLite's shared single-connection
        `StaticPool` test setup, which is why it was not caught until
        real-PostgreSQL testing). Deferring via `after_commit` means the
        job is only ever submitted once the mutation it depends on is
        durable — which also means a caller transaction that rolls back
        *never* enqueues a job at all, resolving what would otherwise be
        an outbox-style gap between marking a projection stale and its
        refresh actually running.

        `job_id` is still returned synchronously: the id is deterministic
        (computed from `target`, not assigned by RQ), so callers can poll
        for it immediately even though the actual submission happens
        slightly later, at commit time."""
        projection = self.projection_repo.get_by_target(
            target.scheme_type, target.scheme_version_id
        )
        now = datetime.now(UTC)
        has_outstanding_job = False

        if projection is None:
            projection = EvaluationProjection(
                scheme_type=target.scheme_type,
                scheme_version_id=target.scheme_version_id,
                status=ProjectionStatus.STALE,
                generation=1,
                recalculation_requested_at=now,
            )
            self.projection_repo.create(projection)
        else:
            projection.generation += 1
            projection.recalculation_requested_at = now
            # `RECALCULATING` (a worker is actively running) and `STALE`
            # (a job for this exact target is already queued or about to
            # be — every transition to `STALE` in this method always
            # arranges an enqueue in the same call) both mean a job is
            # already outstanding: bump the generation only, and trust
            # that outstanding job to read the latest state when it runs
            # (this module's own docstring, "Coalescing / concurrency") —
            # this is what prevents uncontrolled duplicate queue growth
            # from a burst of near-simultaneous requests (§15).
            has_outstanding_job = projection.status in (
                ProjectionStatus.RECALCULATING,
                ProjectionStatus.STALE,
            )
            if not has_outstanding_job:
                projection.status = ProjectionStatus.STALE
            self.projection_repo.save(projection)

        job_id: str | None = None
        if not has_outstanding_job:
            job_id = _refresh_job_id(target)
            generation = projection.generation

            def _submit_after_commit(_session: Session) -> None:
                self._enqueue_refresh_job(
                    target, generation, trigger=trigger, correlation_id=correlation_id
                )

            sa_event.listen(self.db, "after_commit", _submit_after_commit, once=True)

        return RefreshRequestResult(
            scheme_type=target.scheme_type,
            scheme_version_id=target.scheme_version_id,
            status=ProjectionStatus(projection.status),
            generation=projection.generation,
            enqueued=not has_outstanding_job,
            job_id=job_id,
        )

    def _enqueue_refresh_job(
        self,
        target: EvaluationTarget,
        generation: int,
        *,
        trigger: str,
        correlation_id: uuid.UUID | None,
    ) -> str | None:
        # Local import breaks an otherwise-genuine import cycle
        # (service -> worker -> service) — see worker.py's own docstring.
        # `CONTINUOUS_EVALUATION_QUEUE_NAME` is defined once, in
        # worker.py, and imported here rather than duplicated.
        from app.modules.continuous_evaluation.worker import (
            CONTINUOUS_EVALUATION_QUEUE_NAME,
            refresh_evaluation_projection,
        )

        outcome = self.execution_engine.submit(
            refresh_evaluation_projection,
            target.scheme_type.value,
            str(target.scheme_version_id),
            generation,
            trigger,
            str(correlation_id) if correlation_id else None,
            queue_name=CONTINUOUS_EVALUATION_QUEUE_NAME,
            job_id=_refresh_job_id(target),
        )
        return outcome.job_id

    def run_refresh_worker_cycle(
        self,
        target: EvaluationTarget,
        *,
        requested_generation: int,
        trigger: str,
        correlation_id: uuid.UUID | None,
    ) -> None:
        """The background worker's own entry point (`worker.py`). This is
        the one method in this service allowed to commit internally — it
        *is* the top-level transaction owner for a worker job, mirroring
        every existing `bootstrap.py::run_bootstrap`'s own precedent —
        unlike `request_refresh`, which only flushes within a
        caller-owned transaction.

        Never duplicates detector logic: the only calculation performed
        is the single `self.evaluate(request)` call, reusing Sprint 5's
        synchronous core exactly."""
        projection = self.projection_repo.get_by_target(
            target.scheme_type, target.scheme_version_id, for_update=True
        )
        if projection is None:
            # The request that enqueued this job never actually
            # committed (this module's own disclosed outbox-problem
            # limitation) — nothing to refresh.
            return
        if projection.status == ProjectionStatus.RECALCULATING:
            # Another worker already claimed this target; avoid a
            # concurrent double-run. That in-flight worker's own
            # end-of-run generation check already reconciles any newer
            # request (see this module's own docstring).
            return

        claimed_generation = projection.generation
        projection.status = ProjectionStatus.RECALCULATING
        projection.recalculation_started_at = datetime.now(UTC)
        self.projection_repo.save(projection)
        self.db.commit()

        try:
            provider = self.provider_registry.get(target.scheme_type)
            if provider is None:
                raise NoEvaluationRequestProviderError(target.scheme_type)
            request = provider.build_request(target, trigger=trigger)
            result = self.evaluate(request)
        except Exception as exc:  # noqa: BLE001 - recorded as projection failure, not re-raised
            projection = self.projection_repo.get_by_target(
                target.scheme_type, target.scheme_version_id, for_update=True
            )
            projection.status = ProjectionStatus.FAILED
            projection.last_error = str(exc)[:2000]
            projection.last_error_at = datetime.now(UTC)
            projection.recalculation_completed_at = datetime.now(UTC)
            self.projection_repo.save(projection)
            self.db.commit()
            return

        projection = self.projection_repo.get_by_target(
            target.scheme_type, target.scheme_version_id, for_update=True
        )
        projection.evaluated_at = result.evaluated_at
        projection.last_result_snapshot = result.model_dump(mode="json")
        projection.recalculation_completed_at = datetime.now(UTC)
        superseded = projection.generation != claimed_generation
        projection.status = ProjectionStatus.STALE if superseded else ProjectionStatus.CURRENT
        self.projection_repo.save(projection)
        self.db.commit()

        if superseded:
            # A newer invalidation arrived while this evaluation was
            # running — this result is correct as of when it ran, but a
            # newer generation now exists, so one more refresh is
            # required to converge (this module's own docstring,
            # "Coalescing / concurrency").
            self._enqueue_refresh_job(
                target,
                projection.generation,
                trigger="continuous_evaluation.projection.reconciliation",
                correlation_id=correlation_id,
            )

    def get_projection(self, target: EvaluationTarget) -> ProjectionDetail | None:
        """Read-only projection DTO (this sprint's own instructions §20).
        Reconstructs `EvaluationResult` from the frozen JSON snapshot —
        `None` if no evaluation has ever completed successfully."""
        projection = self.projection_repo.get_by_target(
            target.scheme_type, target.scheme_version_id
        )
        if projection is None:
            return None
        last_result = (
            EvaluationResult.model_validate(projection.last_result_snapshot)
            if projection.last_result_snapshot is not None
            else None
        )
        return ProjectionDetail(
            scheme_type=target.scheme_type,
            scheme_version_id=projection.scheme_version_id,
            status=ProjectionStatus(projection.status),
            generation=projection.generation,
            last_result=last_result,
            evaluated_at=projection.evaluated_at,
            recalculation_requested_at=projection.recalculation_requested_at,
            recalculation_started_at=projection.recalculation_started_at,
            recalculation_completed_at=projection.recalculation_completed_at,
            last_error=projection.last_error,
            last_error_at=projection.last_error_at,
            created_at=projection.created_at,
            updated_at=projection.updated_at,
        )


def _refresh_job_id(target: EvaluationTarget) -> str:
    """Deterministic (not RQ-assigned) job identity for one evaluation
    target — lets `request_refresh` return a stable, pollable id
    synchronously even though the actual submission is deferred to
    `self.db`'s own `after_commit` event (see `request_refresh`'s own
    docstring)."""
    return f"continuous_evaluation:{target.scheme_type.value}:{target.scheme_version_id}"
