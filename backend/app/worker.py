"""RQ worker entrypoint — runs jobs enqueued via `app.core.queue.enqueue`.

    python -m app.worker

Run alongside the API server (see `docker-compose.yml`'s `worker` service).
Not imported by the API process itself — this is a separate, standalone
process, per the standard RQ deployment pattern.
"""

from __future__ import annotations

import logging

from rq import Worker

from app.core.queue import _QUEUE_NAME, get_redis_connection


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    connection = get_redis_connection()
    worker = Worker([_QUEUE_NAME], connection=connection)
    worker.work()


if __name__ == "__main__":
    main()
