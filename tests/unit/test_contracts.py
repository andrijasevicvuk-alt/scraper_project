from datetime import UTC, datetime
import unittest

from contracts import CONTRACT_VERSION, ContractValidationError, DetailFetchJob, RawFetchArtifact, validate_contract_payload
from contracts.models import ArtifactStatus, DatasetBatchManifest, DetailReasonCode


NOW = datetime(2026, 7, 27, 12, 0, tzinfo=UTC)
HASH = "a" * 64


class ContractValidationTests(unittest.TestCase):
    def test_detail_job_accepts_approved_reason_and_utc_timestamp(self) -> None:
        job = DetailFetchJob(
            contract_version=CONTRACT_VERSION,
            job_id="job-1",
            crawl_run_id="run-1",
            source_name="fixture_source",
            source_listing_key="listing-1",
            listing_url="https://example.invalid/listing-1",
            reason_code=DetailReasonCode.NEW_LISTING,
            priority=0,
            attempt_number=1,
            max_attempts=3,
            scheduled_at=NOW,
        )
        self.assertEqual(job.reason_code, DetailReasonCode.NEW_LISTING)

    def test_detail_job_rejects_invalid_attempt_range(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "attempt_number"):
            DetailFetchJob(
                contract_version=CONTRACT_VERSION,
                job_id="job-1",
                crawl_run_id="run-1",
                source_name="fixture_source",
                source_listing_key="listing-1",
                listing_url="https://example.invalid/listing-1",
                reason_code=DetailReasonCode.NEW_LISTING,
                priority=0,
                attempt_number=4,
                max_attempts=3,
                scheduled_at=NOW,
            )

    def test_successful_artifact_requires_immutable_snapshot_metadata(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "snapshot_path"):
            RawFetchArtifact(
                contract_version=CONTRACT_VERSION,
                artifact_id="artifact-1",
                job_id="job-1",
                crawl_run_id="run-1",
                source_name="fixture_source",
                source_listing_key="listing-1",
                listing_url="https://example.invalid/listing-1",
                fetched_at=NOW,
                fetch_method="future_protected_adapter",
                acquisition_version="0.1",
                snapshot_path=None,
                content_hash=None,
                response_status=200,
                mime_type="text/html",
                artifact_status=ArtifactStatus.SUCCESS,
            )

    def test_contract_rejects_unsupported_major_version(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "unsupported contract major"):
            DetailFetchJob(
                contract_version="1.0",
                job_id="job-1",
                crawl_run_id="run-1",
                source_name="fixture_source",
                source_listing_key="listing-1",
                listing_url="https://example.invalid/listing-1",
                reason_code=DetailReasonCode.NEW_LISTING,
                priority=0,
                attempt_number=1,
                max_attempts=1,
                scheduled_at=NOW,
            )

    def test_manifest_requires_complete_terminal_accounting(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "record_count"):
            DatasetBatchManifest(
                contract_version=CONTRACT_VERSION,
                batch_id="batch-1",
                batch_version="0.1",
                source_name="fixture_source",
                created_at=NOW,
                snapshot_date="2026-07-27",
                record_count=2,
                terminal_state_counts={"detail_success": 1},
                acquisition_versions=("0.1",),
                parser_versions=("0.1",),
                records_path="batches/batch-1.jsonl",
                records_checksum=HASH,
                manifest_checksum=HASH,
                proxy_bytes_used=0,
                known_limitations=(),
            )

    def test_json_boundary_converts_timestamp_and_enum(self) -> None:
        job = validate_contract_payload(
            "DetailFetchJob",
            {
                "contract_version": CONTRACT_VERSION,
                "job_id": "job-1",
                "crawl_run_id": "run-1",
                "source_name": "fixture_source",
                "source_listing_key": "listing-1",
                "listing_url": "https://example.invalid/listing-1",
                "reason_code": "NEW_LISTING",
                "priority": 0,
                "attempt_number": 1,
                "max_attempts": 1,
                "scheduled_at": "2026-07-27T12:00:00Z",
                "metadata": {},
            },
        )
        self.assertEqual(job.scheduled_at, NOW)

    def test_json_boundary_reports_missing_required_field_as_contract_error(self) -> None:
        with self.assertRaisesRegex(ContractValidationError, "reason_code"):
            validate_contract_payload("DetailFetchJob", {"contract_version": CONTRACT_VERSION})
