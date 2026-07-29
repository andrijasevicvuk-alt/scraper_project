scraper_project

Source-acquisition and source-readiness platform for the Yacht Premium Insurance valuation project.

Purpose

This repository:

discovers in-scope public boat listings;
stores immutable raw snapshots and acquisition telemetry;
parses saved snapshots offline;
maintains crawl jobs, checkpoints and retries;
creates versioned source-level dataset batches;
exports controlled data into YPI raw ingestion.

It does not own final YPI canonical normalization, cross-source deduplication, valuation eligibility, scoring or the web application.

Architecture
source registry
→ discovery
→ protected acquisition adapter
→ raw snapshot and telemetry
→ offline parser
→ source-readiness validation
→ versioned dataset batch
→ YPI raw ingestion
Ownership
Vuk: product owner and merge approval
ChatGPT: architecture, integration and documentation
Gemini: source-specific acquisition research, design and proposed code
Vuk: manually applies, commits and approves Gemini-authored acquisition code
Codex: source-neutral infrastructure, offline parsers, tests and exports

Gemini-authored acquisition paths are protected. Gemini does not commit directly; Vuk controls application and merging, while ChatGPT and Codex review integration.

Current phase

Steps 1–2 complete, Step 3 next

Foundation commands

The current commands are local and perform no source acquisition:

```text
PYTHONPATH=src python -m cli.main health
PYTHONPATH=src python -m cli.main source list
PYTHONPATH=src python -m cli.main contract validate --contract DetailFetchJob --input payload.json
```

`config/sources.example.toml` is an inert configuration example. Copy it locally only when a source registry is ready; it contains no target source endpoint and does not enable acquisition.

Development container

`docker compose run --rm scraper` runs the placeholder health check as a non-root user. The image pre-creates `/app/runtime` for the `scraper` user; the compose file mounts it as a persistent runtime volume and is read-only apart from that volume and temporary files. It does not include any protected acquisition implementation.

Runtime persistence

The local SQLite runtime store uses packaged versioned migrations, WAL mode and one source-neutral writer boundary. See `docs/runtime-state.md` for job-state transitions, recovery, backups and the local-only runtime commands.

Continuous integration runs the full synthetic test suite on Python 3.11. It contains no live target-source acquisition step.
Runtime data

Runtime databases, snapshots, checkpoints, logs, browser profiles, cookies, exports and secrets must never be committed.
