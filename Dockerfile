FROM python:3.13-slim

WORKDIR /app

RUN groupadd --system scraper && useradd --system --gid scraper --create-home scraper

COPY pyproject.toml ./
COPY src ./src

RUN python -m pip install --no-cache-dir --no-build-isolation .

ENV PYTHONPATH=/app/src \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER scraper

CMD ["scraper", "health"]
