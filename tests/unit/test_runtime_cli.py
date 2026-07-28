from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from cli.main import main


class RuntimeCliTests(unittest.TestCase):
    def test_fixture_run_queue_status_and_backup_are_local(self) -> None:
        with TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.sqlite"
            backup = Path(directory) / "backup.sqlite"
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["runtime", "fixture-crawl", "--database", str(database)]), 0)
                self.assertEqual(main(["runtime", "queue-status", "--database", str(database)]), 0)
                self.assertEqual(main(["runtime", "backup", "--database", str(database), "--destination", str(backup)]), 0)
            self.assertTrue(backup.exists())
            self.assertIn("pending", output.getvalue())
