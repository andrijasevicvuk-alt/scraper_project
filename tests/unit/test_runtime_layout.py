from collections import namedtuple
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from orchestration.runtime import RuntimePaths, RuntimeSafetyError, require_free_space


class RuntimeLayoutTests(unittest.TestCase):
    def test_runtime_layout_creates_only_approved_subdirectories(self) -> None:
        with TemporaryDirectory() as directory:
            paths = RuntimePaths.from_root(Path(directory) / "runtime")
            paths.ensure()
            self.assertEqual(
                {path.name for path in paths.root.iterdir()},
                {"database", "checkpoints", "snapshots", "logs", "exports"},
            )

    def test_disk_safety_check_stops_before_work(self) -> None:
        DiskUsage = namedtuple("DiskUsage", "total used free")
        with TemporaryDirectory() as directory:
            with patch("orchestration.runtime.shutil.disk_usage", return_value=DiskUsage(100, 99, 1)):
                with self.assertRaisesRegex(RuntimeSafetyError, "disk safety stop"):
                    require_free_space(Path(directory), 2)
