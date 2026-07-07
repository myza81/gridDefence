"""Execution Engine (Phase 6 architecture refinement) — the configurable
abstraction between business modules and however background-style work
actually executes. No engineering module should import `redis`, `rq`, or
`app.core.queue` directly; it should depend only on this module's
`get_execution_engine()`.

Two modes, selected by `Settings.execution_mode`:

- **"direct"** (default) — the submitted function runs immediately,
  in-process, in the calling thread. No Redis, no RQ, no worker process.
  This project's own primary deployment target is a small engineering
  team (CLAUDE.md; typically fewer than 10 concurrent users) developing on
  company-managed Windows machines where installing Redis may not always
  be possible — Direct mode is the right default for that context, not
  merely a test convenience.
- **"queue"** — the submitted function is enqueued via Redis+RQ
  (`app.core.queue`), exactly as before this refactor. Unchanged production
  behaviour, for deployments that want genuine background execution across
  a separate worker process.

The engineering result of running `run_commit_job(...)` (or any future
submitted function) is identical either way — this module changes nothing
about *what* runs, only *how* its completion is reported back to the
caller. See docs/architecture/psse-integration-module.md §8.9c.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import redis

from app.core.config import get_settings
from app.core.queue import enqueue, fetch_job

logger = logging.getLogger(__name__)


class ExecutionUnavailableError(Exception):
    """Raised when the configured execution mode cannot currently accept
    work (e.g. Queue mode with Redis unreachable). Direct mode never
    raises this — it has no external dependency to fail."""


@dataclass
class ExecutionResult:
    """Uniform outcome of `ExecutionEngine.submit(...)`, regardless of mode.

    `completed=True` means the result (or error) is already available and
    the caller should respond immediately — Direct mode always completes
    this way, synchronously, within `submit` itself. `completed=False`
    means the work was handed to a queue and `job_id` is available to poll
    later via `ExecutionEngine.fetch`.
    """

    completed: bool
    job_id: str | None
    result: Any | None
    error: BaseException | None


class ExecutionEngine(Protocol):
    def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> ExecutionResult: ...

    def fetch(self, job_id: str) -> ExecutionResult | None: ...


class DirectExecutionEngine:
    """Runs the submitted function synchronously, in the calling thread.
    No Redis, no RQ, no worker process — the default execution mode."""

    def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> ExecutionResult:
        try:
            result = func(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - surfaced via ExecutionResult.error, not raised
            return ExecutionResult(completed=True, job_id=None, result=None, error=exc)
        return ExecutionResult(completed=True, job_id=None, result=result, error=None)

    def fetch(self, job_id: str) -> ExecutionResult | None:
        # Direct mode never produces a job_id — there is nothing to poll.
        return None


class QueueExecutionEngine:
    """Enqueues the submitted function via Redis+RQ (`app.core.queue`) —
    unchanged production behaviour from before this refactor."""

    def submit(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> ExecutionResult:
        try:
            job = enqueue(func, *args, **kwargs)
        except redis.exceptions.RedisError as exc:
            logger.error("Execution Engine: queue unavailable — %s", exc)
            raise ExecutionUnavailableError(str(exc)) from exc
        return ExecutionResult(completed=False, job_id=job.id, result=None, error=None)

    def fetch(self, job_id: str) -> ExecutionResult | None:
        job = fetch_job(job_id)
        if job is None:
            return None
        rq_status = job.get_status(refresh=True)
        if rq_status == "finished":
            return ExecutionResult(
                completed=True, job_id=job_id, result=job.return_value(), error=None
            )
        if rq_status == "failed":
            return ExecutionResult(
                completed=True, job_id=job_id, result=None, error=RuntimeError(str(job.exc_info))
            )
        return ExecutionResult(completed=False, job_id=job_id, result=None, error=None)


def get_execution_engine() -> ExecutionEngine:
    """Selects the configured engine. Not cached (unlike `get_settings()`
    itself) — constructing either engine is trivially cheap, and leaving
    this uncached lets a test change `execution_mode` and see the effect
    immediately, without needing to manage a second cache's lifecycle."""
    settings = get_settings()
    if settings.execution_mode == "queue":
        return QueueExecutionEngine()
    return DirectExecutionEngine()
