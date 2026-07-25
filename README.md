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
Gemini: source-specific acquisition design
Antigravity: protected acquisition implementation and execution
Codex: source-neutral infrastructure, offline parsers, tests and exports

Gemini and Antigravity acquisition paths are protected and must not be silently replaced.

Current phase

The current phase is the source-neutral foundation.

No live source adapter, Genesis scrape or production schedule should be implemented yet.

First implementation
Read AGENTS.md.
Read docs/project-boundaries.md.
Read docs/data-contracts.md.
Implement only the source-neutral contracts and project scaffold.
Use fixtures or synthetic data only.
Run tests before proposing the next step.
Runtime data

Runtime databases, snapshots, checkpoints, logs, browser profiles, cookies, exports and secrets must never be committed.