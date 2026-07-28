from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from uuid import uuid4

from contracts.models import ArtifactStatus, CONTRACT_VERSION, DetailFetchJob, DetailReasonCode, DiscoveryObservation, RawFetchArtifact
from database import RuntimeDatabase, RuntimeRepositories
from orchestration import DetailFetchQueue
from orchestration.queue import QueueTransitionError
from storage import backup_database, restore_database


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
HASH = "b" * 64


class RuntimePersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database = RuntimeDatabase(self.root / "runtime.sqlite")
        self.repositories = RuntimeRepositories(self.database)
        self.repositories.sources.upsert("fixture_source", False, "stable_source_key")
        self.run_id = "run-1"
        self.partition_id = "partition-1"
        self.repositories.crawls.create_run(self.run_id, "fixture_source")
        self.repositories.crawls.create_partition(self.partition_id, self.run_id, "fixture_source", "page-1")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _job(self, max_attempts: int = 2) -> DetailFetchJob:
        return DetailFetchJob(
            contract_version=CONTRACT_VERSION,
            job_id=str(uuid4()),
            crawl_run_id=self.run_id,
            source_name="fixture_source",
            source_listing_key="listing-1",
            listing_url="https://example.invalid/listing-1",
            reason_code=DetailReasonCode.NEW_LISTING,
            priority=10,
            attempt_number=1,
            max_attempts=max_attempts,
            scheduled_at=NOW,
            metadata={"fixture": "synthetic"},
        )

    def test_migrates_empty_database_and_enables_wal(self) -> None:
        with self.database.read_connection() as connection:
            tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertIn("detail_fetch_jobs", tables)
        self.assertIn("proxy_usage_ledger", tables)
        self.assertEqual(journal_mode, "wal")

    def test_duplicate_job_insertion_returns_original_job(self) -> None:
        first = self.repositories.jobs.create_idempotent(self._job())
        second = self.repositories.jobs.create_idempotent(self._job())
        self.assertEqual(first, second)
        self.assertEqual(self.repositories.jobs.status_counts(), {"pending": 1})

    def test_job_leasing_and_success_transition(self) -> None:
        job_id = self.repositories.jobs.create_idempotent(self._job())
        queue = DetailFetchQueue(self.database)
        lease = queue.lease_next("worker-a", now=NOW)
        self.assertIsNotNone(lease)
        assert lease is not None
        self.assertEqual(lease.job_id, job_id)
        self.assertIsNone(queue.lease_next("worker-b", now=NOW))
        queue.succeed(job_id, "worker-a", now=NOW)
        self.assertEqual(self.repositories.jobs.status_counts(), {"succeeded": 1})

    def test_conflicting_queue_owner_is_rejected(self) -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO runtime_queue_owner(owner_name, registered_at) VALUES ('other_owner', '2026-07-27T00:00:00Z')"
            )
        with self.assertRaises(QueueTransitionError):
            DetailFetchQueue(self.database)

    def test_retry_exhaustion_prevents_infinite_retries(self) -> None:
        job_id = self.repositories.jobs.create_idempotent(self._job(max_attempts=2))
        queue = DetailFetchQueue(self.database)
        first = queue.lease_next("worker-a", now=NOW)
        assert first is not None
        self.assertEqual(queue.fail(job_id, "worker-a", "synthetic_failure", now=NOW), "pending")
        second = queue.lease_next("worker-b", now=NOW)
        assert second is not None
        self.assertEqual(queue.fail(job_id, "worker-b", "synthetic_failure", now=NOW), "failed_exhausted")
        self.assertIsNone(queue.lease_next("worker-c", now=NOW))
        self.assertEqual(self.repositories.jobs.status_counts(), {"failed_exhausted": 1})

    def test_crash_recovery_requeues_then_exhausts_abandoned_job(self) -> None:
        job_id = self.repositories.jobs.create_idempotent(self._job(max_attempts=2))
        queue = DetailFetchQueue(self.database)
        self.assertIsNotNone(queue.lease_next("worker-a", lease_seconds=1, now=NOW))
        self.assertEqual(queue.recover_abandoned(now=NOW + timedelta(seconds=2)), {"recovered": 1, "exhausted": 0})
        self.assertIsNotNone(queue.lease_next("worker-b", lease_seconds=1, now=NOW + timedelta(seconds=2)))
        self.assertEqual(queue.recover_abandoned(now=NOW + timedelta(seconds=4)), {"recovered": 0, "exhausted": 1})
        self.assertEqual(self.repositories.jobs.status_counts(), {"failed_exhausted": 1})
        self.assertEqual(job_id, job_id)  # Keeps the identity under test explicit.

    def test_checkpoint_resume_survives_new_repository_instance(self) -> None:
        self.repositories.checkpoints.save(self.run_id, self.partition_id, "page-3")
        restarted = RuntimeRepositories(RuntimeDatabase(self.root / "runtime.sqlite"))
        self.assertEqual(restarted.checkpoints.load(self.run_id, self.partition_id), "page-3")

    def test_observations_are_append_only_and_snapshots_are_immutable(self) -> None:
        observation = DiscoveryObservation(
            contract_version=CONTRACT_VERSION,
            crawl_run_id=self.run_id,
            source_name="fixture_source",
            source_listing_key="listing-1",
            listing_url="https://example.invalid/listing-1",
            observed_at=NOW,
            visible_title="Synthetic listing",
            visible_price_text=None,
            visible_currency=None,
            visible_specs={},
            visible_status="observed",
            card_fingerprint=None,
            discovery_partition="page-1",
        )
        observation_id = self.repositories.observations.append(observation)
        job_id = self.repositories.jobs.create_idempotent(self._job())
        self.repositories.snapshots.record(
            RawFetchArtifact(
                contract_version=CONTRACT_VERSION,
                artifact_id="artifact-1",
                job_id=job_id,
                crawl_run_id=self.run_id,
                source_name="fixture_source",
                source_listing_key="listing-1",
                listing_url="https://example.invalid/listing-1",
                fetched_at=NOW,
                fetch_method="synthetic",
                acquisition_version="0.1",
                snapshot_path="snapshots/artifact-1.html",
                content_hash=HASH,
                response_status=200,
                mime_type="text/html",
                artifact_status=ArtifactStatus.SUCCESS,
            )
        )
        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.write_transaction() as connection:
                connection.execute("UPDATE discovery_observations SET visible_title='changed' WHERE observation_id=?", (observation_id,))
        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.write_transaction() as connection:
                connection.execute("UPDATE raw_snapshot_manifests SET snapshot_path='changed' WHERE artifact_id='artifact-1'")

    def test_backup_and_restore_preserve_queue_state(self) -> None:
        self.repositories.jobs.create_idempotent(self._job())
        backup_path = backup_database(self.database, self.root / "backup.sqlite")
        restored_path = restore_database(backup_path, self.root / "restored.sqlite")
        restored = RuntimeRepositories(RuntimeDatabase(restored_path))
        self.assertEqual(restored.jobs.status_counts(), {"pending": 1})
