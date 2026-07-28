# Runtime State

Status: verified by synthetic SQLite tests.

The local runtime database is a source-neutral operational store. It records source registry state, crawl runs and partitions, append-only discovery observations, detail jobs and attempts, checkpoints, snapshot manifests, parser runs, proxy byte ledger entries, and dataset-batch manifests. It does not acquire sources, parse snapshots, normalize YPI records, deduplicate sources, or calculate valuation outcomes.

## Migration and writer policy

`migrations/0001_runtime_schema.sql` is the initial versioned schema. Each applied migration is recorded with a SHA-256 checksum in `schema_migrations`; changing an applied migration fails safely.

SQLite connections enable WAL mode, foreign keys, full synchronous writes, and a busy timeout. `RuntimeDatabase.write_transaction()` is the one in-process writer boundary and uses `BEGIN IMMEDIATE`; SQLite serializes external processes. Queue leasing and retry transitions are implemented only by `DetailFetchQueue`.

## Detail job state transitions

```text
pending --lease--> processing --success--> succeeded
                           |--failure (attempts remain)--> pending
                           |--failure at max_attempts--> failed_exhausted
                           |--expired lease--> pending or failed_exhausted
```

Each lease records an attempt before a worker receives the job. Expired processing leases are classified as abandoned; they are requeued only while `attempt_count < max_attempts`. Job creation is idempotent by `(crawl_run_id, source_name, source_listing_key, reason_code)`.

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
