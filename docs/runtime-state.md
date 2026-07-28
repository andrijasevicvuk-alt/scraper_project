# Runtime State

Status: verified by synthetic SQLite tests.

The local runtime database is a source-neutral operational store. It records source registry state, crawl runs and partitions, append-only discovery observations, detail jobs and attempts, checkpoints, snapshot manifests, parser runs, proxy byte ledger entries, and dataset-batch manifests. It does not acquire sources, parse snapshots, normalize YPI records, deduplicate sources, or calculate valuation outcomes.

## Migration and writer policy

`migrations/0001_runtime_schema.sql` is the initial versioned schema. Each applied migration is recorded with a SHA-256 checksum in `schema_migrations`; changing an applied migration fails safely.

SQLite connections enable WAL mode, foreign keys, full synchronous writes, and a busy timeout. `RuntimeDatabase.write_transaction()` is the one in-process writer boundary and uses `BEGIN IMMEDIATE`; SQLite serializes external processes. Queue leasing and retry transitions are implemented only by `DetailFetchQueue`.

The queue-owner registration is a database singleton. Once `source_neutral_orchestrator` registers, database triggers reject a second, modified, or deleted registration.

## Detail job state transitions

```text
pending --lease--> processing --success--> succeeded
                           |--failure (attempts remain)--> pending
                           |--failure at max_attempts--> failed_exhausted
                           |--expired lease--> pending or failed_exhausted
```

Each lease records an attempt before a worker receives the job. Expired processing leases are classified as abandoned; they are requeued only while `attempt_count < max_attempts`. Job creation is idempotent by `(crawl_run_id, source_name, source_listing_key, reason_code)`.

## Crawl and parser lifecycle

Crawl runs move from `created` to `running`, then to `completed` or `failed`. Partitions move from `pending` to `processing`, then to `completed` or `failed`. Parser runs move from `running` to `completed` or `failed`. Repository methods reject transitions from any other state and retain timestamps and failure reasons for retrieval after a restart.

Dataset-batch manifests are stored and rehydrated as complete `DatasetBatchManifest` values, including contract version, terminal-state counts, acquisition and parser versions, checksums, proxy byte usage, and known limitations. The database rejects duplicate manifest checksums. Proxy-ledger rows are append-only operational measurements; aggregation is by source and proxy-pool label.

## Recovery and backups

Runtime commands are local-only and use synthetic fixture records:

```text
scraper runtime fixture-crawl --database runtime/scraper.sqlite
scraper runtime queue-status --database runtime/scraper.sqlite
scraper runtime recover-abandoned --database runtime/scraper.sqlite
scraper runtime proxy-usage --database runtime/scraper.sqlite
scraper runtime backup --database runtime/scraper.sqlite --destination backups/runtime.sqlite
```

The backup command uses SQLite's online backup API and refuses to overwrite an existing destination. Restore tests copy a backup into a new database and verify persisted queue state.
