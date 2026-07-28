from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import sqlite3
import unittest
from uuid import uuid4

from contracts.models import ArtifactStatus, CONTRACT_VERSION, DatasetBatchManifest, DetailFetchJob, DetailReasonCode, RawFetchArtifact
from database import RuntimeDatabase, RuntimeRepositories
from database.repositories import RepositoryStateError
from orchestration import DetailFetchQueue


NOW = datetime(2026, 7, 28, 10, 0, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


class RuntimeHardeningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.database = RuntimeDatabase(Path(self.temporary_directory.name) / "runtime.sqlite")
        self.repositories = RuntimeRepositories(self.database)
        self.repositories.sources.upsert("fixture_source", False, "stable_source_key")
        self.run_id = "hardening-run"
        self.repositories.crawls.create_run(self.run_id, "fixture_source")

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _job(self, listing_key: str) -> str:
        return self.repositories.jobs.create_idempotent(
            DetailFetchJob(
                contract_version=CONTRACT_VERSION,
                job_id=str(uuid4()),
                crawl_run_id=self.run_id,
                source_name="fixture_source",
                source_listing_key=listing_key,
                listing_url=f"https://example.invalid/{listing_key}",
                reason_code=DetailReasonCode.NEW_LISTING,
                priority=0,
                attempt_number=1,
                max_attempts=2,
                scheduled_at=NOW,
                metadata={"fixture": "synthetic"},
            )
        )

    def _artifact(self) -> str:
        job_id = self._job("parser-listing")
        artifact_id = "parser-artifact"
        self.repositories.snapshots.record(
            RawFetchArtifact(
                contract_version=CONTRACT_VERSION,
                artifact_id=artifact_id,
                job_id=job_id,
                crawl_run_id=self.run_id,
                source_name="fixture_source",
                source_listing_key="parser-listing",
                listing_url="https://example.invalid/parser-listing",
                fetched_at=NOW,
                fetch_method="synthetic",
                acquisition_version="0.1",
                snapshot_path="snapshots/parser-artifact.html",
                content_hash=HASH_A,
                response_status=200,
                mime_type="text/html",
                artifact_status=ArtifactStatus.SUCCESS,
            )
        )
        return artifact_id

    def test_crawl_and_partition_lifecycles_retain_current_state(self) -> None:
        self.assertEqual(self.repositories.crawls.get_run(self.run_id)["state"], "created")
        self.repositories.crawls.start(self.run_id)
        self.assertEqual(self.repositories.crawls.get_run(self.run_id)["state"], "running")
        self.repositories.crawls.create_partition("partition-complete", self.run_id, "fixture_source", "page-1")
        self.repositories.crawls.start_partition("partition-complete")
        self.repositories.crawls.complete_partition("partition-complete")
        self.assertEqual(self.repositories.crawls.get_partition("partition-complete")["state"], "completed")
        self.repositories.crawls.create_partition("partition-fail", self.run_id, "fixture_source", "page-2")
        self.repositories.crawls.start_partition("partition-fail")
        self.repositories.crawls.fail_partition("partition-fail")
        self.assertEqual(self.repositories.crawls.get_partition("partition-fail")["state"], "failed")
        self.repositories.crawls.complete(self.run_id)
        self.assertEqual(self.repositories.crawls.get_run(self.run_id)["state"], "completed")
        with self.assertRaises(RepositoryStateError):
            self.repositories.crawls.start(self.run_id)

    def test_crawl_fail_and_invalid_partition_transition(self) -> None:
        self.repositories.crawls.start(self.run_id)
        self.repositories.crawls.fail(self.run_id)
        self.assertEqual(self.repositories.crawls.get_run(self.run_id)["state"], "failed")
        self.repositories.crawls.create_partition("partition-invalid", self.run_id, "fixture_source", "page-3")
        with self.assertRaises(RepositoryStateError):
            self.repositories.crawls.complete_partition("partition-invalid")

    def test_parser_run_complete_fail_retrieve_and_reject_invalid_transition(self) -> None:
        artifact_id = self._artifact()
        complete_id = self.repositories.parser_runs.start(artifact_id, "fixture_parser", "0.1")
        self.repositories.parser_runs.complete(complete_id)
        completed = self.repositories.parser_runs.get(complete_id)
        assert completed is not None
        self.assertEqual(completed["state"], "completed")
        self.assertIsNotNone(completed["finished_at"])
        with self.assertRaises(RepositoryStateError):
            self.repositories.parser_runs.fail(complete_id, "too_late")
        fail_id = self.repositories.parser_runs.start(artifact_id, "fixture_parser", "0.1")
        self.repositories.parser_runs.fail(fail_id, "synthetic_failure")
        failed = self.repositories.parser_runs.get(fail_id)
        assert failed is not None
        self.assertEqual(failed["state"], "failed")
        self.assertEqual(failed["failure_reason"], "synthetic_failure")

    def test_proxy_usage_aggregates_multiple_jobs_and_zero_bytes(self) -> None:
        first_job = self._job("proxy-listing-1")
        second_job = self._job("proxy-listing-2")
        self.repositories.proxy_usage.append(self.run_id, "fixture_source", "pool-a", 10, 30, first_job)
        self.repositories.proxy_usage.append(self.run_id, "fixture_source", "pool-a", 5, 7, second_job)
        self.repositories.proxy_usage.append(self.run_id, "fixture_source", "pool-b", 0, 0)
        self.assertEqual(
            self.repositories.proxy_usage.totals(),
            [
                {"source_name": "fixture_source", "proxy_pool_label": "pool-a", "bytes_sent": 15, "bytes_received": 37},
                {"source_name": "fixture_source", "proxy_pool_label": "pool-b", "bytes_sent": 0, "bytes_received": 0},
            ],
        )
        with self.assertRaisesRegex(ValueError, "bytes_sent"):
            self.repositories.proxy_usage.append(self.run_id, "fixture_source", "pool-a", -1, 0)
        with self.assertRaisesRegex(ValueError, "bytes_received"):
            self.repositories.proxy_usage.append(self.run_id, "fixture_source", "pool-a", 0, -1)

    def test_dataset_manifest_full_round_trip_and_duplicate_checksum_rejection(self) -> None:
        manifest = DatasetBatchManifest(
            contract_version=CONTRACT_VERSION,
            batch_id="batch-1",
            batch_version="0.1",
            source_name="fixture_source",
            created_at=NOW,
            snapshot_date="2026-07-28",
            record_count=3,
            terminal_state_counts={"detail_success": 2, "manual_review": 1},
            acquisition_versions=("acq-0.1", "acq-0.2"),
            parser_versions=("parser-0.1",),
            records_path="batches/batch-1.jsonl",
            records_checksum=HASH_A,
            manifest_checksum=HASH_B,
            proxy_bytes_used=37,
            known_limitations=("synthetic fixture", "no live acquisition"),
        )
        self.repositories.dataset_batches.record(manifest)
        self.assertEqual(self.repositories.dataset_batches.get("batch-1"), manifest)
        duplicate_checksum = DatasetBatchManifest(
            contract_version=CONTRACT_VERSION,
            batch_id="batch-2",
            batch_version="0.1",
            source_name="fixture_source",
            created_at=NOW,
            snapshot_date="2026-07-28",
            record_count=1,
            terminal_state_counts={"detail_success": 1},
            acquisition_versions=("acq-0.2",),
            parser_versions=("parser-0.1",),
            records_path="batches/batch-2.jsonl",
            records_checksum=HASH_A,
            manifest_checksum=HASH_B,
            proxy_bytes_used=0,
            known_limitations=(),
        )
        with self.assertRaises(sqlite3.IntegrityError):
            self.repositories.dataset_batches.record(duplicate_checksum)

    def test_database_rejects_second_queue_owner_registration(self) -> None:
        DetailFetchQueue(self.database)
        with self.assertRaises(sqlite3.IntegrityError):
            with self.database.write_transaction() as connection:
                connection.execute(
                    "INSERT INTO runtime_queue_owner(owner_name, registered_at) VALUES ('second_owner', '2026-07-28T00:00:00Z')"
                )
