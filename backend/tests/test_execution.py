"""Tests for the Execution Engine abstraction (app/core/execution.py) —
Phase 6 architecture refinement, docs/architecture/psse-integration-module.md
§8.9c. Business modules (e.g. psse_integration) never appear here — this
file tests the abstraction itself, in isolation.
"""

from __future__ import annotations

import pytest
import redis

from app.core.config import get_settings
from app.core.execution import (
    DirectExecutionEngine,
    ExecutionUnavailableError,
    QueueExecutionEngine,
    get_execution_engine,
)
from app.core.queue import get_queue


def _add(a: int, b: int) -> int:
    return a + b


def _boom() -> None:
    raise ValueError("deliberate failure")


class TestGetExecutionEngine:
    def test_defaults_to_direct(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(get_settings(), "execution_mode", "direct")
        assert isinstance(get_execution_engine(), DirectExecutionEngine)

    def test_selects_queue_when_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(get_settings(), "execution_mode", "queue")
        assert isinstance(get_execution_engine(), QueueExecutionEngine)


class TestDirectExecutionEngine:
    def test_submit_runs_immediately_and_returns_the_result(self) -> None:
        outcome = DirectExecutionEngine().submit(_add, 2, 3)
        assert outcome.completed is True
        assert outcome.job_id is None
        assert outcome.result == 5
        assert outcome.error is None

    def test_submit_captures_a_raised_exception_rather_than_propagating_it(self) -> None:
        outcome = DirectExecutionEngine().submit(_boom)
        assert outcome.completed is True
        assert outcome.result is None
        assert isinstance(outcome.error, ValueError)

    def test_fetch_always_returns_none(self) -> None:
        # Direct mode never produces a job_id — there is nothing to poll.
        assert DirectExecutionEngine().fetch("anything") is None


class TestQueueExecutionEngine:
    def test_submit_enqueues_and_returns_a_job_id_not_yet_completed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # RQ_ASYNC=false (backend/conftest.py) runs the queue synchronously
        # against fakeredis — no real Redis server or worker needed here.
        outcome = QueueExecutionEngine().submit(_add, 2, 3)
        assert outcome.job_id is not None
        # Whether `completed` is already True depends on RQ's own
        # is_async=False timing; either way, fetch() must resolve it.
        fetched = QueueExecutionEngine().fetch(outcome.job_id)
        assert fetched is not None
        assert fetched.completed is True
        assert fetched.result == 5
        assert fetched.error is None

    def test_fetch_surfaces_a_failed_job_s_error(self) -> None:
        outcome = QueueExecutionEngine().submit(_boom)
        fetched = QueueExecutionEngine().fetch(outcome.job_id)
        assert fetched is not None
        assert fetched.completed is True
        assert fetched.result is None
        assert fetched.error is not None
        assert "deliberate failure" in str(fetched.error)

    def test_fetch_returns_none_for_an_unknown_job_id(self) -> None:
        assert QueueExecutionEngine().fetch("00000000-0000-0000-0000-000000000000") is None

    def test_submit_raises_execution_unavailable_when_redis_is_unreachable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _raise_connection_error(*args: object, **kwargs: object) -> None:
            raise redis.exceptions.ConnectionError("Connection refused")

        monkeypatch.setattr("app.core.execution.enqueue", _raise_connection_error)

        with pytest.raises(ExecutionUnavailableError):
            QueueExecutionEngine().submit(_add, 2, 3)


def test_get_queue_still_usable_directly_for_worker_process_startup() -> None:
    """`app.worker` still calls `app.core.queue.get_queue()`/
    `get_redis_connection()` directly, by design (§8.9c) — the Execution
    Engine abstraction is for business-module callers, not the worker
    process itself, which must remain a plain RQ worker."""
    queue = get_queue()
    assert queue.name == "psse_integration"


class TestQueueNameRouting:
    """Shared Platform Sprint 6 addition: `submit`/`enqueue`/`get_queue`
    gained an optional `queue_name` (default unchanged: the PSS/E
    Integration queue) so a second module (Continuous Evaluation) can own
    an exclusive named queue on the same Redis connection (ADR-023),
    without any existing call site changing behaviour."""

    def test_enqueue_defaults_to_the_existing_psse_integration_queue(self) -> None:
        from app.core.queue import enqueue

        job = enqueue(_add, 2, 3)
        assert job.origin == "psse_integration"

    def test_enqueue_honours_an_explicit_queue_name(self) -> None:
        from app.core.queue import enqueue

        job = enqueue(_add, 2, 3, queue_name="continuous_evaluation")
        assert job.origin == "continuous_evaluation"

    def test_get_queue_honours_an_explicit_queue_name(self) -> None:
        queue = get_queue("continuous_evaluation")
        assert queue.name == "continuous_evaluation"

    def test_queue_execution_engine_submit_routes_to_the_named_queue(self) -> None:
        outcome = QueueExecutionEngine().submit(_add, 2, 3, queue_name="continuous_evaluation")
        fetched = QueueExecutionEngine().fetch(outcome.job_id)
        assert fetched is not None
        assert fetched.result == 5

    def test_queue_execution_engine_submit_without_queue_name_is_unchanged(self) -> None:
        outcome = QueueExecutionEngine().submit(_add, 2, 3)
        assert outcome.job_id is not None
        fetched = QueueExecutionEngine().fetch(outcome.job_id)
        assert fetched is not None
        assert fetched.result == 5

    def test_direct_execution_engine_accepts_and_discards_queue_specific_kwargs(self) -> None:
        outcome = DirectExecutionEngine().submit(
            _add, 2, 3, queue_name="continuous_evaluation", job_id="whatever", retry=None
        )
        assert outcome.completed is True
        assert outcome.result == 5
