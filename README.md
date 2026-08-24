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

Vuk: product owner, approval, application, commit and merge authority

ChatGPT: architecture, system boundaries, review and prompts

Gemini: source-specific research, acquisition blueprints, experiments and source documentation

Jules: protected source-specific implementation and protected tests

Codex: source-neutral infrastructure, authoritative queue, offline parsers, tests, exports and integration review

ChatGPT and Codex may review Jules-authored protected code but must return protected changes as precise Jules repair prompts rather than editing it directly.

Current phase

Steps 1–2 complete, Step 3 next

Foundation commands

The current commands are local and perform no source acquisition:

```text
python -m pip install -e .
python -m unittest discover -s tests -v
scraper health
scraper source list
scraper contract validate --contract DetailFetchJob --input payload.json
```

Run the editable install once from a fresh checkout before invoking the test suite or CLI.

`config/sources.example.toml` is an inert configuration example. Copy it locally only when a source registry is ready; it contains no target source endpoint and does not enable acquisition.

Development container

`docker compose run --rm scraper` runs the source-neutral worker health check as a non-root user. The image pre-creates `/app/runtime` for the `scraper` user; the compose file mounts it as a persistent runtime volume and is read-only apart from that volume and temporary files. The internal-only `fixture-server` service supplies synthetic records for Step 3A. It does not include any protected acquisition implementation.

Runtime persistence

The local SQLite runtime store uses packaged versioned migrations, WAL mode and one source-neutral writer boundary. See `docs/runtime-state.md` for job-state transitions, recovery, backups and the local-only runtime commands.

Continuous integration runs the full synthetic test suite on Python 3.11. It contains no live target-source acquisition step.

## Step 3A: isolated synthetic worker

Step 3A validates the repository and container flow only. It uses an internal synthetic fixture server and the existing SQLite queue; it does not contact a target source. Runtime state is stored under `/app/runtime` in `database`, `checkpoints`, `snapshots`, `logs`, and `exports` subdirectories.

```text
docker compose up -d fixture-server
docker compose run --rm scraper worker health --runtime-dir /app/runtime
docker compose run --rm scraper worker run-synthetic --runtime-dir /app/runtime
docker compose run --rm scraper runtime queue-status --database /app/runtime/database/scraper.sqlite
```

PowerShell helper scripts are in `scripts/`. Step 3B remains a manual ThinkPad-to-Home-PC validation and is not completed by this repository work.
Runtime data

Runtime databases, snapshots, checkpoints, logs, browser profiles, cookies, exports and secrets must never be committed.
