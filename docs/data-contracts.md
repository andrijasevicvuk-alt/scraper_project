Shared Data Contracts

Contract status: v0.1-draft

These contracts connect protected acquisition adapters with the source-neutral platform.

General rules
Use UTC ISO-8601 timestamps.
Use stable string identifiers.
Use null for unknown values.
Preserve original source strings.
Never include credentials, cookies or tokens.
Every payload includes contract_version.
Breaking changes require a version increment and migration plan.
DetailFetchJob

A request for an approved detail acquisition.

Required fields:

contract_version
job_id
crawl_run_id
source_name
source_listing_key
listing_url
reason_code
priority
attempt_number
max_attempts
scheduled_at
metadata

Approved initial reason codes:

NEW_LISTING
NO_DETAIL_SNAPSHOT
PRICE_CHANGE_REQUIRES_DETAIL
CARD_FINGERPRINT_CHANGED
HIGH_PRIORITY_LISTING
CRITICAL_FIELDS_MISSING
STALE_DETAIL_REFRESH
PARSER_VERSION_RECHECK
MISSING_LISTING_VERIFICATION
MANUAL_REPROCESS_REQUEST
DiscoveryObservation

A lightweight observation from a list or discovery page.

Required fields:

contract_version
crawl_run_id
source_name
source_listing_key
listing_url
observed_at
visible_title
visible_price_text
visible_currency
visible_specs
visible_status
card_fingerprint
discovery_partition

Primary identity is:

source_name + source_listing_key

Title and price are change signals, not identity.

RawFetchArtifact

A stored result produced by a protected acquisition adapter.

Required fields:

contract_version
artifact_id
job_id
crawl_run_id
source_name
source_listing_key
listing_url
fetched_at
fetch_method
acquisition_version
snapshot_path
content_hash
response_status
mime_type
artifact_status

A completed snapshot must not be overwritten.

FetchTelemetry

Operational measurements for one acquisition attempt.

Required fields:

contract_version
job_id
source_name
attempt_number
started_at
finished_at
duration_ms
bytes_sent
bytes_received
outcome
error_class
proxy_pool_label

Telemetry must not expose proxy credentials.

ParsedListingCandidate

Offline parser output containing source-level evidence.

Required fields:

contract_version
candidate_id
artifact_id
source_name
source_listing_key
listing_url
parsed_at
parser_name
parser_version
parse_status
raw_fields
field_evidence
field_confidence
warnings
failure_reasons

The parser must not perform final YPI canonical mapping or valuation decisions.

DatasetBatchManifest

Description of one versioned source-level dataset export.

Required fields:

contract_version
batch_id
batch_version
source_name
created_at
snapshot_date
record_count
terminal_state_counts
acquisition_versions
parser_versions
records_path
records_checksum
manifest_checksum
proxy_bytes_used
known_limitations
Compatibility

Consumers must reject unsupported major contract versions.

Additive optional fields may be introduced within the same compatible version. Removing or changing required fields requires a new major version.