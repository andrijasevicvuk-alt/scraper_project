"""Resumable Step 3A synthetic workflow using the existing runtime repositories."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import logging
from pathlib import Path
from collections.abc import Callable
from urllib.parse import urlparse
from urllib.request import urlopen
from uuid import NAMESPACE_URL, uuid5

from contracts.models import (
    ArtifactStatus,
    CONTRACT_VERSION,
    DatasetBatchManifest,
    DetailFetchJob,
    DetailReasonCode,
    DiscoveryObservation,
    RawFetchArtifact,
)
from database import RuntimeDatabase, RuntimeRepositories
from orchestration.queue import DetailFetchQueue

from .runtime import RuntimePaths, require_free_space


_LOCAL_FIXTURE_HOSTS = {"localhost", "127.0.0.1", "fixture-server"}
_SOURCE_NAME = "synthetic_fixture"
_PARTITION_KEY = "synthetic-page-1"


class SyntheticWorkerError(RuntimeError):
    """Raised when a synthetic fixture is invalid or outside the allowed local boundary."""


@dataclass(frozen=True, slots=True)
class SyntheticWorkerResult:
    run_id: str
    state: str
    checkpoint: str
    recovered_abandoned: int
    exhausted_abandoned: int
    snapshot_path: str | None = None
    batch_id: str | None = None

    def as_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)


class SyntheticWorker:
    """Runs only deterministic fixture data through the authoritative SQLite workflow."""

    def __init__(self, runtime_root: Path, fixture_url: str, minimum_free_bytes: int = 1) -> None:
        self.paths = RuntimePaths.from_root(runtime_root)
        self.fixture_url = fixture_url
        self.minimum_free_bytes = minimum_free_bytes
        self.logger = logging.getLogger(__name__)

    @property
    def database_path(self) -> Path:
        return self.paths.database / "scraper.sqlite"

    def health(self) -> dict[str, object]:
        self.paths.ensure()
        free_bytes = require_free_space(self.paths.root, self.minimum_free_bytes)
        repositories = RuntimeRepositories(RuntimeDatabase(self.database_path))
        DetailFetchQueue(repositories.database)
        return {
            "status": "ok",
            "runtime_root": str(self.paths.root),
            "database": str(self.database_path),
            "free_bytes": free_bytes,
        }

    def run(
        self,
        run_id: str,
        *,
        lease_seconds: int = 30,
        stop_after: str | None = None,
        now: datetime | None = None,
        shutdown_requested: Callable[[], bool] | None = None,
    ) -> SyntheticWorkerResult:
        if stop_after not in {None, "discovery", "lease", "graceful_shutdown", "snapshot"}:
            raise ValueError("unsupported synthetic stop point")
        self.paths.ensure()
        require_free_space(self.paths.root, self.minimum_free_bytes)
        current = now or datetime.now(UTC)
        database = RuntimeDatabase(self.database_path)
        repositories = RuntimeRepositories(database)
        queue = DetailFetchQueue(database)
        recovery = queue.recover_abandoned(now=current)
        partition_id = str(uuid5(NAMESPACE_URL, f"{run_id}:partition"))
        job_id = str(uuid5(NAMESPACE_URL, f"{run_id}:detail-job"))
        artifact_id = str(uuid5(NAMESPACE_URL, f"{run_id}:artifact"))
        batch_id = str(uuid5(NAMESPACE_URL, f"{run_id}:batch"))

        self._ensure_run(repositories, run_id, partition_id)
        checkpoint = repositories.checkpoints.load(run_id, partition_id)
        if checkpoint is None:
            self._discover_and_queue(repositories, run_id, partition_id, job_id, current)
            checkpoint = "queued"
            if stop_after == "discovery":
                return self._result(run_id, "interrupted", checkpoint, recovery)

        if checkpoint == "queued":
            lease = queue.lease_next("synthetic-worker", lease_seconds=lease_seconds, now=current)
            if lease is None:
                return self._result(run_id, "waiting_for_lease", checkpoint, recovery)
            if stop_after == "lease":
                return self._result(run_id, "interrupted", checkpoint, recovery)
            if stop_after == "graceful_shutdown" or (shutdown_requested is not None and shutdown_requested()):
                queue.fail(lease.job_id, "synthetic-worker", "graceful_shutdown", now=current)
                return self._result(run_id, "gracefully_stopped", checkpoint, recovery)
            snapshot_path = self._record_snapshot(repositories, artifact_id, lease.job_id, run_id, current)
            queue.succeed(lease.job_id, "synthetic-worker", now=current)
            repositories.checkpoints.save(run_id, partition_id, "snapshot-recorded")
            checkpoint = "snapshot-recorded"
            if stop_after == "snapshot":
                return self._result(run_id, "interrupted", checkpoint, recovery, snapshot_path=snapshot_path)

        snapshot_path = str(self.paths.snapshots / f"{artifact_id}.json")
        if checkpoint == "snapshot-recorded":
            parser_run_id = repositories.parser_runs.start(artifact_id, "synthetic_placeholder", "0.1")
            repositories.parser_runs.complete(parser_run_id)
            repositories.checkpoints.save(run_id, partition_id, "parser-completed")
            checkpoint = "parser-completed"

        if checkpoint == "parser-completed":
            self._record_batch(repositories, batch_id, run_id, artifact_id, current)
            repositories.checkpoints.save(run_id, partition_id, "batch-recorded")
            checkpoint = "batch-recorded"

        if checkpoint == "batch-recorded":
            run = repositories.crawls.get_run(run_id)
            if run is not None and run["state"] == "running":
                repositories.crawls.complete_partition(partition_id)
                repositories.crawls.complete(run_id)
            repositories.checkpoints.save(run_id, partition_id, "completed")
            checkpoint = "completed"

        return self._result(run_id, "completed", checkpoint, recovery, snapshot_path=snapshot_path, batch_id=batch_id)

    def _ensure_run(self, repositories: RuntimeRepositories, run_id: str, partition_id: str) -> None:
        repositories.sources.upsert(_SOURCE_NAME, False, "stable_source_key", "Synthetic Step 3A fixture only.")
        run = repositories.crawls.get_run(run_id)
        if run is None:
            repositories.crawls.create_run(run_id, _SOURCE_NAME, run_kind="synthetic_step3a")
            repositories.crawls.start(run_id)
        partition = repositories.crawls.get_partition(partition_id)
        if partition is None:
            repositories.crawls.create_partition(partition_id, run_id, _SOURCE_NAME, _PARTITION_KEY)
            partition = repositories.crawls.get_partition(partition_id)
        if partition is not None and partition["state"] == "pending":
            repositories.crawls.start_partition(partition_id)

    def _discover_and_queue(
        self, repositories: RuntimeRepositories, run_id: str, partition_id: str, job_id: str, current: datetime
    ) -> None:
        fixture = self._fetch_fixture()
        listing_key = _text(fixture, "source_listing_key")
        listing_url = _text(fixture, "listing_url")
        repositories.observations.append(
            DiscoveryObservation(
                contract_version=CONTRACT_VERSION,
                crawl_run_id=run_id,
                source_name=_text(fixture, "source_name"),
                source_listing_key=listing_key,
                listing_url=listing_url,
                observed_at=current,
                visible_title=_optional_text(fixture, "visible_title"),
                visible_price_text=_optional_text(fixture, "visible_price_text"),
                visible_currency=_optional_text(fixture, "visible_currency"),
                visible_specs=_string_mapping(fixture.get("visible_specs")),
                visible_status=_optional_text(fixture, "visible_status"),
                card_fingerprint=_optional_text(fixture, "card_fingerprint"),
                discovery_partition=_PARTITION_KEY,
            )
        )
        repositories.jobs.create_idempotent(
            DetailFetchJob(
                contract_version=CONTRACT_VERSION,
                job_id=job_id,
                crawl_run_id=run_id,
                source_name=_SOURCE_NAME,
                source_listing_key=listing_key,
                listing_url=listing_url,
                reason_code=DetailReasonCode.NEW_LISTING,
                priority=0,
                attempt_number=1,
                max_attempts=2,
                scheduled_at=current,
                metadata={"fixture": "synthetic_step3a"},
            )
        )
        repositories.checkpoints.save(run_id, partition_id, "queued")
        self.logger.info("synthetic discovery queued", extra={"event": "synthetic_discovery"})

    def _record_snapshot(
        self, repositories: RuntimeRepositories, artifact_id: str, job_id: str, run_id: str, current: datetime
    ) -> str:
        body = _canonical_json_bytes(self._fetch_fixture())
        digest = sha256(body).hexdigest()
        snapshot_path = self.paths.snapshots / f"{artifact_id}.json"
        if snapshot_path.exists():
            if sha256(snapshot_path.read_bytes()).hexdigest() != digest:
                raise SyntheticWorkerError("synthetic snapshot already exists with different content")
        else:
            try:
                with snapshot_path.open("xb") as snapshot_file:
                    snapshot_file.write(body)
            except FileExistsError as exc:
                raise SyntheticWorkerError("synthetic snapshot creation raced unexpectedly") from exc
        fixture = json.loads(body)
        existing = repositories.snapshots.get(artifact_id)
        if existing is None:
            repositories.snapshots.record(
                RawFetchArtifact(
                    contract_version=CONTRACT_VERSION,
                    artifact_id=artifact_id,
                    job_id=job_id,
                    crawl_run_id=run_id,
                    source_name=_SOURCE_NAME,
                    source_listing_key=_text(fixture, "source_listing_key"),
                    listing_url=_text(fixture, "listing_url"),
                    fetched_at=current,
                    fetch_method="local_synthetic_fixture",
                    acquisition_version="step3a-synthetic-0.1",
                    snapshot_path=str(snapshot_path),
                    content_hash=digest,
                    response_status=200,
                    mime_type="application/json",
                    artifact_status=ArtifactStatus.SUCCESS,
                )
            )
        self.logger.info("synthetic snapshot recorded", extra={"event": "synthetic_snapshot"})
        return str(snapshot_path)

    def _record_batch(
        self, repositories: RuntimeRepositories, batch_id: str, run_id: str, artifact_id: str, current: datetime
    ) -> None:
        if repositories.dataset_batches.get(batch_id) is not None:
            return
        records_path = self.paths.exports / f"{batch_id}.jsonl"
        record = {"artifact_id": artifact_id, "crawl_run_id": run_id, "source_name": _SOURCE_NAME}
        records = _canonical_json_bytes(record) + b"\n"
        if records_path.exists():
            if records_path.read_bytes() != records:
                raise SyntheticWorkerError("synthetic dataset records already exist with different content")
        else:
            with records_path.open("xb") as records_file:
                records_file.write(records)
        records_checksum = sha256(records).hexdigest()
        manifest_input = {
            "batch_id": batch_id,
            "records_checksum": records_checksum,
            "run_id": run_id,
            "source_name": _SOURCE_NAME,
        }
        manifest_checksum = sha256(_canonical_json_bytes(manifest_input)).hexdigest()
        repositories.dataset_batches.record(
            DatasetBatchManifest(
                contract_version=CONTRACT_VERSION,
                batch_id=batch_id,
                batch_version="step3a-synthetic-0.1",
                source_name=_SOURCE_NAME,
                created_at=current,
                snapshot_date=current.date().isoformat(),
                record_count=1,
                terminal_state_counts={"detail_success": 1},
                acquisition_versions=("step3a-synthetic-0.1",),
                parser_versions=("synthetic_placeholder-0.1",),
                records_path=str(records_path),
                records_checksum=records_checksum,
                manifest_checksum=manifest_checksum,
                proxy_bytes_used=0,
                known_limitations=("synthetic local fixture only", "no live acquisition"),
            )
        )
        self.logger.info("synthetic dataset batch recorded", extra={"event": "synthetic_batch"})

    def _fetch_fixture(self) -> dict[str, object]:
        parsed = urlparse(self.fixture_url)
        if parsed.scheme != "http" or parsed.hostname not in _LOCAL_FIXTURE_HOSTS:
            raise SyntheticWorkerError("synthetic fixture URL must use an approved local fixture host")
        try:
            with urlopen(self.fixture_url, timeout=5) as response:  # noqa: S310 - host allowlist above
                if response.status != 200:
                    raise SyntheticWorkerError(f"synthetic fixture returned HTTP {response.status}")
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SyntheticWorkerError("synthetic fixture is unavailable or invalid") from exc
        if not isinstance(payload, dict) or _text(payload, "source_name") != _SOURCE_NAME:
            raise SyntheticWorkerError("synthetic fixture has an unsupported source identity")
        return payload

    @staticmethod
    def _result(
        run_id: str,
        state: str,
        checkpoint: str,
        recovery: dict[str, int],
        *,
        snapshot_path: str | None = None,
        batch_id: str | None = None,
    ) -> SyntheticWorkerResult:
        return SyntheticWorkerResult(
            run_id=run_id,
            state=state,
            checkpoint=checkpoint,
            recovered_abandoned=recovery["recovered"],
            exhausted_abandoned=recovery["exhausted"],
            snapshot_path=snapshot_path,
            batch_id=batch_id,
        )


def _canonical_json_bytes(payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _text(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise SyntheticWorkerError(f"synthetic fixture requires non-empty {key}")
    return value


def _optional_text(payload: dict[str, object], key: str) -> str | None:
    value = payload.get(key)
    if value is None or isinstance(value, str):
        return value
    raise SyntheticWorkerError(f"synthetic fixture {key} must be a string or null")


def _string_mapping(value: object) -> dict[str, str | None]:
    if not isinstance(value, dict) or not all(isinstance(key, str) and (item is None or isinstance(item, str)) for key, item in value.items()):
        raise SyntheticWorkerError("synthetic fixture visible_specs must be a string mapping")
    return value
