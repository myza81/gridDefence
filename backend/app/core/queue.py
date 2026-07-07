"""Redis/RQ job queue — introduced in Phase 4 (PSS/E Integration), the
first module with genuinely heavy async computation (RAW file parsing/
validation and EquipmentTopologyMap matching; implementation-plan.md §4,
psse-integration-module.md §18).

`settings.rq_async = False` (the test-environment default, see
`app/core/config.py`) makes `enqueue()` run the job function synchronously,
in-process, via RQ's own `Queue(is_async=False)` mode — no real Redis
server or background worker needed for correctness tests. Production runs
with `rq_async = True` against a real Redis connection and a real
`app.worker` process (`docker-compose.yml`'s `worker` service).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import redis
from rq import Queue
from rq.job import Job

from app.core.config import get_settings

_QUEUE_NAME = "psse_integration"


@lru_cache
def get_redis_connection() -> redis.Redis:
    """Cached so the same connection (or, in tests, the same `fakeredis`
    instance) is reused across calls within one process.

    `settings.rq_async = False` (the test-environment default) hands back
    a `fakeredis.FakeRedis` instance instead of a real `redis.Redis`
    connection — this, combined with RQ's own `Queue(is_async=False)` mode
    (`get_queue()` below), is what lets the whole test suite run without a
    real Redis server or worker process.
    """
    settings = get_settings()
    if not settings.rq_async:
        import fakeredis

        return fakeredis.FakeRedis()
    return redis.Redis.from_url(settings.redis_url)


def get_queue() -> Queue:
    settings = get_settings()
    return Queue(_QUEUE_NAME, connection=get_redis_connection(), is_async=settings.rq_async)


def enqueue(func: Any, *args: Any, **kwargs: Any) -> Job:
    """Enqueues `func(*args, **kwargs)` on the PSS/E Integration queue.
    Returns the RQ `Job` — callers read `.id` for polling (`fetch_job`)."""
    return get_queue().enqueue(func, *args, **kwargs)


def fetch_job(job_id: str) -> Job | None:
    try:
        return Job.fetch(job_id, connection=get_redis_connection())
    except Exception:  # noqa: BLE001 - rq raises its own NoSuchJobError subclass
        return None
