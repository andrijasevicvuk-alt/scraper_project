# Runtime State

Status: verified by synthetic SQLite tests.

The local runtime database is a source-neutral operational store. It records source registry state, crawl runs and partitions, append-only discovery observations, detail jobs and attempts, checkpoints, snapshot manifests, parser runs, proxy byte ledger entries, and dataset-batch manifests. It does not acquire sources, parse snapshots, normalize YPI records, deduplicate sources, or calculate valuation outcomes.

## Migration and writer policy

`src/database/migrations/` is the canonical packaged source for versioned SQL migrations. Each applied migration is recorded with a SHA-256 checksum in `schema_migrations`; changing an applied migration fails safely. The same package resources are used by editable/source installs, wheel installs, and the Docker image.

SQLite connections enable WAL mode, foreign keys, full synchronous writes, and a busy timeout. `RuntimeDatabase.write_transaction()` is the one in-process writer boundary and uses `BEGIN IMMEDIATE`; SQLite serializes external processes. Queue leasing and retry transitions are implemented only by `DetailFetchQueue`.

The queue-owner registration is a database singleton. Once `source_neutral_orchestrator` registers, database triggers reject a second, modified, or deleted registration.

External acquisition and crawler tools must not create a second authoritative queue, retry system, checkpoint store or terminal-state owner.

Crawlee, Scrapling, browser runtimes and protected source adapters may operate only through the existing source-neutral contracts and orchestration boundary.


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

## Step 3A synthetic worker

The source-neutral worker uses one persistent runtime root with `database`, `checkpoints`, `snapshots`, `logs`, and `exports` subdirectories. It rejects a run before queue work if the configured minimum free disk space is not available. Its synthetic fixture endpoint accepts only local `localhost`, `127.0.0.1`, or Docker-internal `fixture-server` hosts.

The synthetic workflow is:

```text
synthetic discovery -> DiscoveryObservation -> DetailFetchJob
-> immutable snapshot + RawFetchArtifact -> parser-run placeholder
-> DatasetBatchManifest
```

It always uses the existing `RuntimeDatabase`, `DetailFetchQueue`, checkpoint repository, snapshot repository, parser-run repository, and dataset-batch repository. It does not create a second queue or database. A graceful shutdown returns an active lease to `pending`; an abrupt simulated interruption leaves an expired lease for the existing abandoned-job recovery path. Restarting resumes from the saved checkpoint without recreating a completed snapshot or batch.

Step 3A is repository and container validation only. Step 3B is the separate manual ThinkPad-to-Home-PC procedure: start the fixture service and worker on the Home PC, run the health and runtime-status scripts from the ThinkPad, stop the worker, restart it, and verify the same queue, snapshot, and batch state remain present.

PowerShell helpers are deliberately thin wrappers around the same Compose commands:

```text
scripts/Start-Worker.ps1
scripts/Get-WorkerHealth.ps1
scripts/Get-RuntimeStatus.ps1
scripts/Stop-Worker.ps1
scripts/Resume-Worker.ps1
```

`Stop-Worker.ps1` does not remove volumes. Step 3B must use the same named runtime volume after a stop/restart and record the observed queue, snapshot, and batch identifiers before it can be marked complete.
