"""Logging setup that redacts common credential-shaped values."""

from __future__ import annotations

import logging
import re


class _RedactingFilter(logging.Filter):
    _patterns = (
        re.compile(r"(?i)(authorization:\\s*)([^\\s]+)"),
        re.compile(r"(?i)([?&](?:token|api_key|password|secret)=)([^&\\s]+)"),
    )

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        for pattern in self._patterns:
            message = pattern.sub(r"\\1[REDACTED]", message)
        record.msg = message
        record.args = ()
        return True


def configure_logging(level: int = logging.INFO) -> None:
    """Configure concise stderr logging without loading secret-bearing configuration."""
    handler = logging.StreamHandler()
    handler.addFilter(_RedactingFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
