"""Typed v0.1 contracts shared by protected adapters and neutral platform code."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, ClassVar

from .validation import (
    CONTRACT_VERSION,
    ContractValidationError,
    parse_utc_timestamp,
    reject_sensitive_keys,
    require_contract_version,
    require_http_url,
    require_non_negative_int,
    require_sha256,
    require_text,
    require_utc_timestamp,
)


class DetailReasonCode(StrEnum):
    NEW_LISTING = "NEW_LISTING"
    NO_DETAIL_SNAPSHOT = "NO_DETAIL_SNAPSHOT"
    PRICE_CHANGE_REQUIRES_DETAIL = "PRICE_CHANGE_REQUIRES_DETAIL"
    CARD_FINGERPRINT_CHANGED = "CARD_FINGERPRINT_CHANGED"
    HIGH_PRIORITY_LISTING = "HIGH_PRIORITY_LISTING"
    CRITICAL_FIELDS_MISSING = "CRITICAL_FIELDS_MISSING"
    STALE_DETAIL_REFRESH = "STALE_DETAIL_REFRESH"
    PARSER_VERSION_RECHECK = "PARSER_VERSION_RECHECK"
    MISSING_LISTING_VERIFICATION = "MISSING_LISTING_VERIFICATION"
    MANUAL_REPROCESS_REQUEST = "MANUAL_REPROCESS_REQUEST"


class ArtifactStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    NOT_MODIFIED = "NOT_MODIFIED"


class TelemetryOutcome(StrEnum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ParseStatus(StrEnum):
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


def _require_source_identity(source_name: str, source_listing_key: str, listing_url: str) -> None:
    require_text(source_name, "source_name")
    require_text(source_listing_key, "source_listing_key")
    require_http_url(listing_url, "listing_url")


def _parse_enum(enum_type: type[StrEnum], value: object, field_name: str) -> StrEnum:
    try:
        return enum_type(value)  # type: ignore[arg-type]
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} has unsupported value {value!r}") from exc


@dataclass(frozen=True, slots=True)
class DetailFetchJob:
    contract_version: str
    job_id: str
    crawl_run_id: str
    source_name: str
    source_listing_key: str
    listing_url: str
    reason_code: DetailReasonCode
    priority: int
    attempt_number: int
    max_attempts: int
    scheduled_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_contract_version(self.contract_version)
        for field_name in ("job_id", "crawl_run_id"):
            require_text(getattr(self, field_name), field_name)
        _require_source_identity(self.source_name, self.source_listing_key, self.listing_url)
        require_non_negative_int(self.priority, "priority")
        require_non_negative_int(self.attempt_number, "attempt_number")
        require_non_negative_int(self.max_attempts, "max_attempts")
        if self.attempt_number < 1 or self.max_attempts < self.attempt_number:
            raise ContractValidationError("attempt_number must be at least 1 and no greater than max_attempts")
        if not isinstance(self.reason_code, DetailReasonCode):
            raise ContractValidationError("reason_code must be an approved DetailReasonCode")
        require_utc_timestamp(self.scheduled_at, "scheduled_at")
        if not isinstance(self.metadata, Mapping):
            raise ContractValidationError("metadata must be an object")
        reject_sensitive_keys(self.metadata, "metadata")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "DetailFetchJob":
        data = dict(payload)
        data["reason_code"] = _parse_enum(DetailReasonCode, data.get("reason_code"), "reason_code")
        data["scheduled_at"] = parse_utc_timestamp(data.get("scheduled_at"), "scheduled_at")
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class DiscoveryObservation:
    contract_version: str
    crawl_run_id: str
    source_name: str
    source_listing_key: str
    listing_url: str
    observed_at: datetime
    visible_title: str | None
    visible_price_text: str | None
    visible_currency: str | None
    visible_specs: Mapping[str, str | None]
    visible_status: str | None
    card_fingerprint: str | None
    discovery_partition: str

    def __post_init__(self) -> None:
        require_contract_version(self.contract_version)
        require_text(self.crawl_run_id, "crawl_run_id")
        _require_source_identity(self.source_name, self.source_listing_key, self.listing_url)
        require_utc_timestamp(self.observed_at, "observed_at")
        require_text(self.discovery_partition, "discovery_partition")
        if not isinstance(self.visible_specs, Mapping):
            raise ContractValidationError("visible_specs must be an object")
        reject_sensitive_keys(self.visible_specs, "visible_specs")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "DiscoveryObservation":
        data = dict(payload)
        data["observed_at"] = parse_utc_timestamp(data.get("observed_at"), "observed_at")
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class RawFetchArtifact:
    contract_version: str
    artifact_id: str
    job_id: str
    crawl_run_id: str
    source_name: str
    source_listing_key: str
    listing_url: str
    fetched_at: datetime
    fetch_method: str
    acquisition_version: str
    snapshot_path: str | None
    content_hash: str | None
    response_status: int | None
    mime_type: str | None
    artifact_status: ArtifactStatus

    def __post_init__(self) -> None:
        require_contract_version(self.contract_version)
        for field_name in ("artifact_id", "job_id", "crawl_run_id", "fetch_method", "acquisition_version"):
            require_text(getattr(self, field_name), field_name)
        _require_source_identity(self.source_name, self.source_listing_key, self.listing_url)
        require_utc_timestamp(self.fetched_at, "fetched_at")
        if self.response_status is not None:
            if isinstance(self.response_status, bool) or not isinstance(self.response_status, int) or not 100 <= self.response_status <= 599:
                raise ContractValidationError("response_status must be an HTTP status code or null")
        if not isinstance(self.artifact_status, ArtifactStatus):
            raise ContractValidationError("artifact_status must be an approved ArtifactStatus")
        if self.artifact_status is ArtifactStatus.SUCCESS:
            if self.snapshot_path is None or self.content_hash is None:
                raise ContractValidationError("successful artifacts require immutable snapshot_path and content_hash")
            require_text(self.snapshot_path, "snapshot_path")
            require_sha256(self.content_hash, "content_hash")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "RawFetchArtifact":
        data = dict(payload)
        data["fetched_at"] = parse_utc_timestamp(data.get("fetched_at"), "fetched_at")
        data["artifact_status"] = _parse_enum(ArtifactStatus, data.get("artifact_status"), "artifact_status")
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class FetchTelemetry:
    contract_version: str
    job_id: str
    source_name: str
    attempt_number: int
    started_at: datetime
    finished_at: datetime
    duration_ms: int
    bytes_sent: int
    bytes_received: int
    outcome: TelemetryOutcome
    error_class: str | None
    proxy_pool_label: str

    def __post_init__(self) -> None:
        require_contract_version(self.contract_version)
        require_text(self.job_id, "job_id")
        require_text(self.source_name, "source_name")
        require_non_negative_int(self.attempt_number, "attempt_number")
        if self.attempt_number < 1:
            raise ContractValidationError("attempt_number must be at least 1")
        require_utc_timestamp(self.started_at, "started_at")
        require_utc_timestamp(self.finished_at, "finished_at")
        if self.finished_at < self.started_at:
            raise ContractValidationError("finished_at cannot be earlier than started_at")
        for field_name in ("duration_ms", "bytes_sent", "bytes_received"):
            require_non_negative_int(getattr(self, field_name), field_name)
        require_text(self.proxy_pool_label, "proxy_pool_label")
        if not isinstance(self.outcome, TelemetryOutcome):
            raise ContractValidationError("outcome must be an approved TelemetryOutcome")
        if self.outcome is TelemetryOutcome.SUCCESS and self.error_class is not None:
            raise ContractValidationError("successful telemetry cannot include error_class")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "FetchTelemetry":
        data = dict(payload)
        data["started_at"] = parse_utc_timestamp(data.get("started_at"), "started_at")
        data["finished_at"] = parse_utc_timestamp(data.get("finished_at"), "finished_at")
        data["outcome"] = _parse_enum(TelemetryOutcome, data.get("outcome"), "outcome")
        return cls(**data)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class ParsedListingCandidate:
    contract_version: str
    candidate_id: str
    artifact_id: str
    source_name: str
    source_listing_key: str
    listing_url: str
    parsed_at: datetime
    parser_name: str
    parser_version: str
    parse_status: ParseStatus
    raw_fields: Mapping[str, str | None]
    field_evidence: Mapping[str, Mapping[str, str | None]]
    field_confidence: Mapping[str, float]
    warnings: tuple[str, ...]
    failure_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        require_contract_version(self.contract_version)
        for field_name in ("candidate_id", "artifact_id", "parser_name", "parser_version"):
            require_text(getattr(self, field_name), field_name)
        _require_source_identity(self.source_name, self.source_listing_key, self.listing_url)
        require_utc_timestamp(self.parsed_at, "parsed_at")
        if not isinstance(self.parse_status, ParseStatus):
            raise ContractValidationError("parse_status must be an approved ParseStatus")
        if not all(isinstance(value, Mapping) for value in (self.raw_fields, self.field_evidence, self.field_confidence)):
            raise ContractValidationError("raw_fields, field_evidence and field_confidence must be objects")
        for field_name, confidence in self.field_confidence.items():
            require_text(field_name, "field_confidence key")
            if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                raise ContractValidationError("field_confidence values must be between 0 and 1")
        reject_sensitive_keys(self.raw_fields, "raw_fields")
        reject_sensitive_keys(self.field_evidence, "field_evidence")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "ParsedListingCandidate":
        data = dict(payload)
        data["parsed_at"] = parse_utc_timestamp(data.get("parsed_at"), "parsed_at")
        data["parse_status"] = _parse_enum(ParseStatus, data.get("parse_status"), "parse_status")
        data["warnings"] = tuple(data.get("warnings", ()))
        data["failure_reasons"] = tuple(data.get("failure_reasons", ()))
        return cls(**data)  # type: ignore[arg-type]


_TERMINAL_STATES = {
    "detail_success",
    "list_only_accepted",
    "excluded_with_reason",
    "failed_classified",
    "manual_review",
}


@dataclass(frozen=True, slots=True)
class DatasetBatchManifest:
    contract_version: str
    batch_id: str
    batch_version: str
    source_name: str
    created_at: datetime
    snapshot_date: str
    record_count: int
    terminal_state_counts: Mapping[str, int]
    acquisition_versions: tuple[str, ...]
    parser_versions: tuple[str, ...]
    records_path: str
    records_checksum: str
    manifest_checksum: str
    proxy_bytes_used: int
    known_limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        require_contract_version(self.contract_version)
        for field_name in ("batch_id", "batch_version", "source_name", "snapshot_date", "records_path"):
            require_text(getattr(self, field_name), field_name)
        require_utc_timestamp(self.created_at, "created_at")
        require_non_negative_int(self.record_count, "record_count")
        require_non_negative_int(self.proxy_bytes_used, "proxy_bytes_used")
        require_sha256(self.records_checksum, "records_checksum")
        require_sha256(self.manifest_checksum, "manifest_checksum")
        if not isinstance(self.terminal_state_counts, Mapping):
            raise ContractValidationError("terminal_state_counts must be an object")
        if set(self.terminal_state_counts) - _TERMINAL_STATES:
            raise ContractValidationError("terminal_state_counts contains an unsupported terminal state")
        for state, count in self.terminal_state_counts.items():
            require_non_negative_int(count, f"terminal_state_counts.{state}")
        if sum(self.terminal_state_counts.values()) != self.record_count:
            raise ContractValidationError("record_count must equal the sum of terminal_state_counts")

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "DatasetBatchManifest":
        data = dict(payload)
        data["created_at"] = parse_utc_timestamp(data.get("created_at"), "created_at")
        data["acquisition_versions"] = tuple(data.get("acquisition_versions", ()))
        data["parser_versions"] = tuple(data.get("parser_versions", ()))
        data["known_limitations"] = tuple(data.get("known_limitations", ()))
        return cls(**data)  # type: ignore[arg-type]


CONTRACT_TYPES: ClassVar[dict[str, type[Any]]] = {
    "DetailFetchJob": DetailFetchJob,
    "DiscoveryObservation": DiscoveryObservation,
    "RawFetchArtifact": RawFetchArtifact,
    "FetchTelemetry": FetchTelemetry,
    "ParsedListingCandidate": ParsedListingCandidate,
    "DatasetBatchManifest": DatasetBatchManifest,
}
