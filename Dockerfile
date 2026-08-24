FROM python:3.13-slim

WORKDIR /app

RUN groupadd --system scraper \
    && useradd --system --gid scraper --create-home scraper \
    && install --directory --owner=scraper --group=scraper \
        /app/runtime \
        /app/runtime/database \
        /app/runtime/checkpoints \
        /app/runtime/snapshots \
        /app/runtime/logs \
        /app/runtime/exports

COPY src ./src

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN python -c "from database.migrations import migration_directory; assert {path.name for path in migration_directory().iterdir()} >= {'0001_runtime_schema.sql', '0002_persistence_hardening.sql'}"

USER scraper

ENTRYPOINT ["python", "-m", "cli.main"]
CMD ["worker", "health", "--runtime-dir", "/app/runtime"]
