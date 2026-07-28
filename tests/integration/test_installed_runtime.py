from pathlib import Path
from shutil import copytree, ignore_patterns
from tempfile import TemporaryDirectory
import os
import subprocess
import sys
import unittest


class InstalledRuntimeTests(unittest.TestCase):
    def test_installed_package_applies_all_migrations_and_runs_cli_outside_checkout(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        with TemporaryDirectory() as directory:
            temporary_root = Path(directory)
            package_source = temporary_root / "package-source"
            target = temporary_root / "installed"
            copytree(
                project_root,
                package_source,
                ignore=ignore_patterns(".git", "runtime", "__pycache__", "*.egg-info"),
            )
            install_environment = os.environ.copy()
            install_environment.pop("PYTHONPATH", None)
            install_environment["PIP_CACHE_DIR"] = str(temporary_root / "pip-cache")
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "install",
                    "--no-deps",
                    "--no-build-isolation",
                    "--target",
                    str(target),
                    str(package_source),
                ],
                cwd=temporary_root,
                env=install_environment,
                check=True,
                capture_output=True,
                text=True,
            )
            database_path = temporary_root / "installed-runtime.sqlite"
            cli_database_path = temporary_root / "installed-cli.sqlite"
            script = f"""
import sys
from pathlib import Path
sys.path.insert(0, {str(target)!r})
from database import RuntimeDatabase, RuntimeRepositories
from cli.main import main

database = RuntimeDatabase(Path({str(database_path)!r}))
RuntimeRepositories(database)
with database.read_connection() as connection:
    versions = [row[0] for row in connection.execute('SELECT version FROM schema_migrations ORDER BY version')]
assert versions == ['0001', '0002'], versions
assert main(['runtime', 'fixture-crawl', '--database', {str(cli_database_path)!r}]) == 0
"""
            subprocess.run(
                [sys.executable, "-c", script],
                cwd=temporary_root,
                env=install_environment,
                check=True,
                capture_output=True,
                text=True,
            )
