from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from uuid import NAMESPACE_URL, uuid5

from database import RuntimeDatabase, RuntimeRepositories
from orchestration.fixture_server import serve_synthetic_fixture
from orchestration.synthetic_worker import SyntheticWorker


NOW = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)


class SyntheticWorkerIntegrationTests(unittest.TestCase):
    def test_synthetic_flow_persists_snapshot_manifest_parser_and_batch(self) -> None:
        with TemporaryDirectory() as directory, serve_synthetic_fixture() as fixture_url:
            worker = SyntheticWorker(Path(directory) / "runtime", fixture_url)
            health = worker.health()
            result = worker.run("step3a-complete", now=NOW)
            self.assertEqual(health["status"], "ok")
            self.assertEqual(result.state, "completed")
            self.assertEqual(result.checkpoint, "completed")
            self.assertIsNotNone(result.snapshot_path)
            self.assertTrue(Path(result.snapshot_path or "").exists())
            repositories = RuntimeRepositories(RuntimeDatabase(worker.database_path))
            assert result.batch_id is not None
            manifest = repositories.dataset_batches.get(result.batch_id)
            self.assertIsNotNone(manifest)
            assert manifest is not None
            self.assertEqual(manifest.terminal_state_counts, {"detail_success": 1})
            self.assertTrue(Path(manifest.records_path).exists())
            restarted = worker.run("step3a-complete", now=NOW + timedelta(seconds=1))
            self.assertEqual(restarted.state, "completed")
            with repositories.database.read_connection() as connection:
                snapshot_count = connection.execute("SELECT COUNT(*) FROM raw_snapshot_manifests").fetchone()[0]
                batch_count = connection.execute("SELECT COUNT(*) FROM dataset_batch_manifests").fetchone()[0]
            self.assertEqual((snapshot_count, batch_count), (1, 1))

    def test_abandoned_lease_recovers_and_resumes_without_losing_work(self) -> None:
        with TemporaryDirectory() as directory, serve_synthetic_fixture() as fixture_url:
            worker = SyntheticWorker(Path(directory) / "runtime", fixture_url)
            interrupted = worker.run("step3a-recovery", now=NOW, lease_seconds=1, stop_after="lease")
            self.assertEqual(interrupted.state, "interrupted")
            resumed = worker.run("step3a-recovery", now=NOW + timedelta(seconds=2), lease_seconds=1)
            self.assertEqual(resumed.state, "completed")
            self.assertEqual(resumed.recovered_abandoned, 1)
            repositories = RuntimeRepositories(RuntimeDatabase(worker.database_path))
            self.assertEqual(repositories.jobs.status_counts(), {"succeeded": 1})
            run_id = "step3a-recovery"
            job_id = str(uuid5(NAMESPACE_URL, f"{run_id}:detail-job"))
            with repositories.database.read_connection() as connection:
                attempts = connection.execute(
                    "SELECT attempt_count FROM detail_fetch_jobs WHERE job_id=?", (job_id,)
                ).fetchone()["attempt_count"]
            self.assertEqual(attempts, 2)

    def test_graceful_shutdown_requeues_the_current_lease_for_resume(self) -> None:
        with TemporaryDirectory() as directory, serve_synthetic_fixture() as fixture_url:
            worker = SyntheticWorker(Path(directory) / "runtime", fixture_url)
            stopped = worker.run("step3a-graceful", now=NOW, stop_after="graceful_shutdown")
            self.assertEqual(stopped.state, "gracefully_stopped")
            repositories = RuntimeRepositories(RuntimeDatabase(worker.database_path))
            self.assertEqual(repositories.jobs.status_counts(), {"pending": 1})
            resumed = worker.run("step3a-graceful", now=NOW + timedelta(seconds=1))
            self.assertEqual(resumed.state, "completed")
