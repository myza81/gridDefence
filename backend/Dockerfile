# Development image. Not a production build (no multi-stage slimming, dev
# dependencies included) — sufficient for docker-compose local development
# per Phase 0's scope (docs/architecture/implementation-plan.md).
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY tests ./tests

RUN pip install --no-cache-dir -e ".[dev]"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
