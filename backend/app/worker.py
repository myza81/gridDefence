"""RQ worker entrypoint — runs jobs enqueued via `app.core.queue.enqueue`.

    python -m app.worker

Run alongside the API server (see `docker-compose.yml`'s `worker` service).
Not imported by the API process itself — this is a separate, standalone
process, per the standard RQ deployment pattern.

Listens on two named queues (Shared Platform Sprint 6 addition): PSS/E
Integration's own pre-existing queue, and Continuous Evaluation's own
exclusively-owned queue (ADR-023 — "one shared queue... owned exclusively
by the Continuous Evaluation Engine module"). One worker process, one
`rq.Worker`, two queue names — no new worker/infrastructure component.
"""

from __future__ import annotations

import logging

from rq import Worker

from app.core.queue import _QUEUE_NAME, get_redis_connection
from app.modules.continuous_evaluation.worker import CONTINUOUS_EVALUATION_QUEUE_NAME


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    connection = get_redis_connection()
    worker = Worker([_QUEUE_NAME, CONTINUOUS_EVALUATION_QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
