FROM python:3.13-slim

WORKDIR /app

RUN groupadd --system scraper \
    && useradd --system --gid scraper --create-home scraper \
    && install --directory --owner=scraper --group=scraper /app/runtime

COPY src ./src

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER scraper

CMD ["python", "-m", "cli.main", "health"]
