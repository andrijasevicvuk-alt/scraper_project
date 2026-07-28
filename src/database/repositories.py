"""Repositories for durable source-neutral runtime records."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
import json
from typing import Any
from uuid import uuid4

from contracts.models import DatasetBatchManifest, DetailFetchJob, DiscoveryObservation, RawFetchArtifact

from .connection import RuntimeDatabase
from .migrations import apply_migrations


def _now() -> datetime:
    return datetime.now(UTC)


def _timestamp(value: datetime | None = None) -> str:
    return (value or _now()).astimezone(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class JobLease:
    job_id: str
    source_name: str
    source_listing_key: str
    reason_code: str
    attempt_number: int
    max_attempts: int
    lease_owner: str
    lease_expires_at: str


class SourceRegistryRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def upsert(self, source_name: str, enabled: bool, identity_strategy: str, identity_notes: str | None = None) -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO source_registry_state(source_name, enabled, identity_strategy, identity_notes, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(source_name) DO UPDATE SET enabled=excluded.enabled, "
                "identity_strategy=excluded.identity_strategy, identity_notes=excluded.identity_notes, "
                "updated_at=excluded.updated_at",
                (source_name, int(enabled), identity_strategy, identity_notes, _timestamp()),
            )


class CrawlRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def create_run(self, crawl_run_id: str, source_name: str, run_kind: str = "fixture") -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO crawl_runs(crawl_run_id, source_name, run_kind, state, started_at, created_at) "
                "VALUES (?, ?, ?, 'running', ?, ?)",
                (crawl_run_id, source_name, run_kind, _timestamp(), _timestamp()),
            )

    def create_partition(self, partition_id: str, crawl_run_id: str, source_name: str, partition_key: str) -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO crawl_partitions(partition_id, crawl_run_id, source_name, partition_key, state, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
                (partition_id, crawl_run_id, source_name, partition_key, _timestamp(), _timestamp()),
            )


class ObservationRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def append(self, observation: DiscoveryObservation, observation_id: str | None = None) -> str:
        record_id = observation_id or str(uuid4())
        observed_at = _timestamp(observation.observed_at)
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO source_listing_identity(source_name, source_listing_key, listing_url, first_observed_at, last_observed_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(source_name, source_listing_key) DO UPDATE SET "
                "listing_url=excluded.listing_url, last_observed_at=excluded.last_observed_at",
                (observation.source_name, observation.source_listing_key, observation.listing_url, observed_at, observed_at),
            )
            connection.execute(
                "INSERT INTO discovery_observations(observation_id, crawl_run_id, source_name, source_listing_key, listing_url, "
                "observed_at, visible_title, visible_price_text, visible_currency, visible_specs_json, visible_status, "
                "card_fingerprint, discovery_partition) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id, observation.crawl_run_id, observation.source_name, observation.source_listing_key,
                    observation.listing_url, observed_at, observation.visible_title, observation.visible_price_text,
                    observation.visible_currency, json.dumps(dict(observation.visible_specs), sort_keys=True),
                    observation.visible_status, observation.card_fingerprint, observation.discovery_partition,
                ),
            )
        return record_id


class JobRepository:
    """Creates jobs and exposes status; queue transitions live only in orchestration.queue."""

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def create_idempotent(self, job: DetailFetchJob) -> str:
        scheduled_at = _timestamp(job.scheduled_at)
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO source_listing_identity(source_name, source_listing_key, listing_url, first_observed_at, last_observed_at) "
                "VALUES (?, ?, ?, ?, ?) ON CONFLICT(source_name, source_listing_key) DO NOTHING",
                (job.source_name, job.source_listing_key, job.listing_url, scheduled_at, scheduled_at),
            )
            connection.execute(
                "INSERT INTO detail_fetch_jobs(job_id, crawl_run_id, source_name, source_listing_key, listing_url, reason_code, "
                "priority, max_attempts, state, scheduled_at, metadata_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?) "
                "ON CONFLICT(crawl_run_id, source_name, source_listing_key, reason_code) DO NOTHING",
                (
                    job.job_id, job.crawl_run_id, job.source_name, job.source_listing_key, job.listing_url,
                    job.reason_code.value, job.priority, job.max_attempts, scheduled_at,
                    json.dumps(dict(job.metadata), sort_keys=True), _timestamp(), _timestamp(),
                ),
            )
            existing = connection.execute(
                "SELECT job_id FROM detail_fetch_jobs WHERE crawl_run_id=? AND source_name=? "
                "AND source_listing_key=? AND reason_code=?",
                (job.crawl_run_id, job.source_name, job.source_listing_key, job.reason_code.value),
            ).fetchone()
        assert existing is not None
        return str(existing["job_id"])

    def status_counts(self) -> dict[str, int]:
        with self.database.read_connection() as connection:
            rows = connection.execute("SELECT state, COUNT(*) AS count FROM detail_fetch_jobs GROUP BY state").fetchall()
        return {str(row["state"]): int(row["count"]) for row in rows}


class CheckpointRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def save(self, crawl_run_id: str, partition_id: str, checkpoint_value: str) -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO checkpoints(crawl_run_id, partition_id, checkpoint_value, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(crawl_run_id, partition_id) DO UPDATE SET checkpoint_value=excluded.checkpoint_value, "
                "updated_at=excluded.updated_at",
                (crawl_run_id, partition_id, checkpoint_value, _timestamp()),
            )

    def load(self, crawl_run_id: str, partition_id: str) -> str | None:
        with self.database.read_connection() as connection:
            row = connection.execute(
                "SELECT checkpoint_value FROM checkpoints WHERE crawl_run_id=? AND partition_id=?",
                (crawl_run_id, partition_id),
            ).fetchone()
        return None if row is None else str(row["checkpoint_value"])


class SnapshotRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def record(self, artifact: RawFetchArtifact) -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO raw_snapshot_manifests(artifact_id, job_id, crawl_run_id, source_name, source_listing_key, "
                "listing_url, fetched_at, fetch_method, acquisition_version, snapshot_path, content_hash, response_status, "
                "mime_type, artifact_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    artifact.artifact_id, artifact.job_id, artifact.crawl_run_id, artifact.source_name,
                    artifact.source_listing_key, artifact.listing_url, _timestamp(artifact.fetched_at), artifact.fetch_method,
                    artifact.acquisition_version, artifact.snapshot_path, artifact.content_hash, artifact.response_status,
                    artifact.mime_type, artifact.artifact_status.value,
                ),
            )


class ParserRunRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def start(self, artifact_id: str, parser_name: str, parser_version: str) -> str:
        parser_run_id = str(uuid4())
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO parser_runs(parser_run_id, artifact_id, parser_name, parser_version, started_at, state) "
                "VALUES (?, ?, ?, ?, ?, 'running')",
                (parser_run_id, artifact_id, parser_name, parser_version, _timestamp()),
            )
        return parser_run_id


class ProxyUsageRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def append(self, crawl_run_id: str, source_name: str, proxy_pool_label: str, bytes_sent: int, bytes_received: int, job_id: str | None = None) -> str:
        ledger_id = str(uuid4())
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO proxy_usage_ledger(ledger_id, crawl_run_id, job_id, source_name, proxy_pool_label, "
                "recorded_at, bytes_sent, bytes_received) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (ledger_id, crawl_run_id, job_id, source_name, proxy_pool_label, _timestamp(), bytes_sent, bytes_received),
            )
        return ledger_id

    def totals(self) -> list[dict[str, Any]]:
        with self.database.read_connection() as connection:
            rows = connection.execute(
                "SELECT source_name, proxy_pool_label, SUM(bytes_sent) AS bytes_sent, SUM(bytes_received) AS bytes_received "
                "FROM proxy_usage_ledger GROUP BY source_name, proxy_pool_label ORDER BY source_name, proxy_pool_label"
            ).fetchall()
        return [dict(row) for row in rows]


class DatasetBatchRepository:
    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database

    def record(self, manifest: DatasetBatchManifest) -> None:
        with self.database.write_transaction() as connection:
            connection.execute(
                "INSERT INTO dataset_batch_manifests(batch_id, source_name, batch_version, created_at, manifest_json, manifest_checksum) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    manifest.batch_id, manifest.source_name, manifest.batch_version, _timestamp(manifest.created_at),
                    json.dumps({"record_count": manifest.record_count, "records_path": manifest.records_path}, sort_keys=True),
                    manifest.manifest_checksum,
                ),
            )


class RuntimeRepositories:
    """Initialise a database and expose its source-neutral repositories."""

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database
        apply_migrations(database)
        self.sources = SourceRegistryRepository(database)
        self.crawls = CrawlRepository(database)
        self.observations = ObservationRepository(database)
        self.jobs = JobRepository(database)
        self.checkpoints = CheckpointRepository(database)
        self.snapshots = SnapshotRepository(database)
        self.parser_runs = ParserRunRepository(database)
        self.proxy_usage = ProxyUsageRepository(database)
        self.dataset_batches = DatasetBatchRepository(database)
