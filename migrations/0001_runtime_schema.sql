-- Source-neutral local runtime state. No acquisition or YPI tables belong here.
CREATE TABLE IF NOT EXISTS source_registry_state (
    source_name TEXT PRIMARY KEY,
    enabled INTEGER NOT NULL CHECK (enabled IN (0, 1)),
    identity_strategy TEXT NOT NULL,
    identity_notes TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_runs (
    crawl_run_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL REFERENCES source_registry_state(source_name),
    run_kind TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('created', 'running', 'completed', 'failed')),
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crawl_partitions (
    partition_id TEXT PRIMARY KEY,
    crawl_run_id TEXT NOT NULL REFERENCES crawl_runs(crawl_run_id),
    source_name TEXT NOT NULL,
    partition_key TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('pending', 'processing', 'completed', 'failed')),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (crawl_run_id, partition_key)
);

CREATE TABLE IF NOT EXISTS source_listing_identity (
    source_name TEXT NOT NULL,
    source_listing_key TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    PRIMARY KEY (source_name, source_listing_key)
);

CREATE TABLE IF NOT EXISTS discovery_observations (
    observation_id TEXT PRIMARY KEY,
    crawl_run_id TEXT NOT NULL REFERENCES crawl_runs(crawl_run_id),
    source_name TEXT NOT NULL,
    source_listing_key TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    visible_title TEXT,
    visible_price_text TEXT,
    visible_currency TEXT,
    visible_specs_json TEXT NOT NULL,
    visible_status TEXT,
    card_fingerprint TEXT,
    discovery_partition TEXT NOT NULL,
    FOREIGN KEY (source_name, source_listing_key)
        REFERENCES source_listing_identity(source_name, source_listing_key)
);
CREATE INDEX IF NOT EXISTS idx_discovery_observations_identity
    ON discovery_observations(source_name, source_listing_key, observed_at);

CREATE TABLE IF NOT EXISTS detail_fetch_jobs (
    job_id TEXT PRIMARY KEY,
    crawl_run_id TEXT NOT NULL REFERENCES crawl_runs(crawl_run_id),
    source_name TEXT NOT NULL,
    source_listing_key TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    priority INTEGER NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    max_attempts INTEGER NOT NULL CHECK (max_attempts >= 1),
    state TEXT NOT NULL CHECK (state IN ('pending', 'processing', 'succeeded', 'failed_exhausted')),
    scheduled_at TEXT NOT NULL,
    lease_owner TEXT,
    lease_expires_at TEXT,
    metadata_json TEXT NOT NULL,
    last_error_class TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (crawl_run_id, source_name, source_listing_key, reason_code),
    FOREIGN KEY (source_name, source_listing_key)
        REFERENCES source_listing_identity(source_name, source_listing_key)
);
CREATE INDEX IF NOT EXISTS idx_detail_fetch_jobs_queue
    ON detail_fetch_jobs(state, scheduled_at, priority DESC, created_at);

CREATE TABLE IF NOT EXISTS job_attempts (
    job_attempt_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES detail_fetch_jobs(job_id),
    attempt_number INTEGER NOT NULL,
    worker_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    outcome TEXT CHECK (outcome IN ('succeeded', 'failed_retryable', 'failed_exhausted', 'abandoned')),
    error_class TEXT,
    UNIQUE (job_id, attempt_number)
);

CREATE TABLE IF NOT EXISTS checkpoints (
    crawl_run_id TEXT NOT NULL REFERENCES crawl_runs(crawl_run_id),
    partition_id TEXT NOT NULL REFERENCES crawl_partitions(partition_id),
    checkpoint_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (crawl_run_id, partition_id)
);

CREATE TABLE IF NOT EXISTS raw_snapshot_manifests (
    artifact_id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES detail_fetch_jobs(job_id),
    crawl_run_id TEXT NOT NULL REFERENCES crawl_runs(crawl_run_id),
    source_name TEXT NOT NULL,
    source_listing_key TEXT NOT NULL,
    listing_url TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    fetch_method TEXT NOT NULL,
    acquisition_version TEXT NOT NULL,
    snapshot_path TEXT,
    content_hash TEXT,
    response_status INTEGER,
    mime_type TEXT,
    artifact_status TEXT NOT NULL,
    UNIQUE (job_id, artifact_id)
);

CREATE TABLE IF NOT EXISTS parser_runs (
    parser_run_id TEXT PRIMARY KEY,
    artifact_id TEXT NOT NULL REFERENCES raw_snapshot_manifests(artifact_id),
    parser_name TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    state TEXT NOT NULL CHECK (state IN ('running', 'completed', 'failed')),
    failure_reason TEXT
);

CREATE TABLE IF NOT EXISTS proxy_usage_ledger (
    ledger_id TEXT PRIMARY KEY,
    crawl_run_id TEXT NOT NULL REFERENCES crawl_runs(crawl_run_id),
    job_id TEXT REFERENCES detail_fetch_jobs(job_id),
    source_name TEXT NOT NULL,
    proxy_pool_label TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    bytes_sent INTEGER NOT NULL CHECK (bytes_sent >= 0),
    bytes_received INTEGER NOT NULL CHECK (bytes_received >= 0)
);
CREATE INDEX IF NOT EXISTS idx_proxy_usage_source ON proxy_usage_ledger(source_name, recorded_at);

CREATE TABLE IF NOT EXISTS dataset_batch_manifests (
    batch_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    batch_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_checksum TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS runtime_queue_owner (
    owner_name TEXT PRIMARY KEY,
    registered_at TEXT NOT NULL
);

CREATE TRIGGER IF NOT EXISTS discovery_observations_append_only_update
BEFORE UPDATE ON discovery_observations
BEGIN
    SELECT RAISE(ABORT, 'discovery observations are append-only');
END;

CREATE TRIGGER IF NOT EXISTS discovery_observations_append_only_delete
BEFORE DELETE ON discovery_observations
BEGIN
    SELECT RAISE(ABORT, 'discovery observations are append-only');
END;

CREATE TRIGGER IF NOT EXISTS completed_snapshots_immutable
BEFORE UPDATE ON raw_snapshot_manifests
WHEN OLD.artifact_status = 'SUCCESS'
BEGIN
    SELECT RAISE(ABORT, 'completed snapshot manifests are immutable');
END;

CREATE TRIGGER IF NOT EXISTS completed_snapshots_not_deleted
BEFORE DELETE ON raw_snapshot_manifests
WHEN OLD.artifact_status = 'SUCCESS'
BEGIN
    SELECT RAISE(ABORT, 'completed snapshot manifests are immutable');
END;
