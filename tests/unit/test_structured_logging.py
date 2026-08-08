from pathlib import Path
from tempfile import TemporaryDirectory
import logging
import unittest

from scraper_logging import configure_logging


class StructuredLoggingTests(unittest.TestCase):
    def test_structured_log_redacts_credential_shaped_values(self) -> None:
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "worker.jsonl"
            configure_logging(structured=True, log_path=log_path)
            logging.getLogger("synthetic").warning(
                "Authorization: Bearer private-value?token=another-private-value",
                extra={"event": "synthetic_test"},
            )
            content = log_path.read_text(encoding="utf-8")
            configure_logging()
            logging.shutdown()
        self.assertIn('"event": "synthetic_test"', content)
        self.assertIn("[REDACTED]", content)
        self.assertNotIn("private-value", content)
        self.assertNotIn("another-private-value", content)
