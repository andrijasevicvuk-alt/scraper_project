"""Logging setup that redacts common credential-shaped values."""

from __future__ import annotations

import logging
import json
from pathlib import Path
import re


class _RedactingFilter(logging.Filter):
    _patterns = (
        re.compile(r"(?i)(authorization:\s*)(.+)$"),
        re.compile(r"(?i)([?&](?:token|api_key|password|secret)=)([^&\s]+)"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\1[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


class _JsonFormatter(logging.Formatter):
    """Emit concise structured records without serialising arbitrary extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "event", None)
        if isinstance(event, str):
            payload["event"] = event
        return json.dumps(payload, sort_keys=True)


def configure_logging(
    level: int = logging.INFO, *, structured: bool = False, log_path: Path | None = None
) -> None:
    """Configure redacted stderr logging and an optional persistent structured log."""
    handler = logging.StreamHandler()
    handler.addFilter(_RedactingFilter())
    formatter: logging.Formatter
    formatter = _JsonFormatter() if structured else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    handler.setFormatter(formatter)
    root = logging.getLogger()
    for existing_handler in root.handlers:
        root.removeHandler(existing_handler)
        existing_handler.close()
    root.addHandler(handler)
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.addFilter(_RedactingFilter())
        file_handler.setFormatter(_JsonFormatter())
        root.addHandler(file_handler)
    root.setLevel(level)
