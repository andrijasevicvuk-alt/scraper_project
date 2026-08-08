# AGENTS.md

## 1. Project purpose

`scraper_project` is the source-acquisition and source-readiness platform for the Yacht Premium Insurance valuation project.

Its responsibilities are:

* discovering in-scope public boat listings;
* acquiring source-level raw artifacts through protected adapters;
* storing immutable raw snapshots and acquisition telemetry;
* parsing saved source artifacts offline;
* maintaining crawl state, checkpoints and retries;
* producing source-readiness signals;
* creating versioned dataset batches;
* exporting controlled source-level records to YPI raw ingestion.

The scraper project does not own final valuation business logic.

## 2. Main architecture

The required data flow is:

```text
source registry
→ discovery
→ DiscoveryObservation
→ detail-fetch decision
→ DetailFetchJob
→ protected acquisition adapter
→ RawFetchArtifact + FetchTelemetry
→ immutable raw snapshot
→ offline parser
→ ParsedListingCandidate
→ source-level validation and readiness signals
→ versioned dataset batch
→ YPI raw ingestion
```

YPI separately owns:

```text
raw ingestion
→ canonical normalization
→ cross-source deduplication
→ final quality eligibility
→ valuation-ready publication
→ scoring
→ valuation UI
```

Do not merge these responsibilities.

## 3. Source-of-truth hierarchy

When sources conflict, use this order:

1. running code and passing tests;
2. versioned migrations and schemas;
3. raw snapshots and dataset manifests;
4. crawl telemetry and run reports;
5. canonical repository documentation;
6. Scraper Project Second Brain notes;
7. archived notes and previous conversations.

Obsidian is the project memory and operating manual. It does not override verified repository or runtime evidence.

## 4. Ownership

### Vuk

Vuk is the product owner and merge gate.

Only Vuk may approve:

* architecture changes;
* protected-path changes;
* source scope;
* alternative-source adoption;
* pilot acceptance;
* Genesis execution;
* changes to shared contracts;
* merges into `main`.

No agent may silently replace an approved component.

### ChatGPT

ChatGPT owns planning and review for:

* system architecture;
* shared boundaries;
* data contracts;
* queue and state-machine design;
* source registry;
* Genesis and routine logic;
* proxy and storage budgeting;
* normalization and quality architecture;
* dedupe-candidate architecture;
* YPI handoff;
* Codex prompts;
* documentation reviews;
* Obsidian changes.

ChatGPT must review protected acquisition through its outputs and contracts, not rewrite its internal implementation.

### Gemini

Gemini owns source-specific research, acquisition blueprints, experiment plans and source documentation.

Gemini may:

* research approved sources;
* define discovery and partition strategies;
* define source identity;
* select source-specific acquisition modes;
* evaluate experimental acquisition and interaction tools;
* define sessions, telemetry, fixtures and pilot limits;
* prepare an implementation-ready prompt and protected file map for Jules.

Gemini does not directly implement or commit protected production code.

### Jules

Jules owns protected source-specific implementation and protected tests.

Jules may implement approved work inside:

src/acquisition/protected/**
src/acquisition/custom_adapter/**
src/acquisition/protected_adapters/**
docker/protected/**
config/protected/**
tests/protected_acquisition/**

Jules implements the approved Gemini blueprint. Jules must not silently redesign the source strategy or replace existing protected work.

Vuk applies, commits and merges accepted Jules files or patches.

### Antigravity

Antigravity is not part of the current project workflow.

Old Gemini-to-Antigravity implementation handoffs are superseded.

### Codex

Codex is the source-neutral platform engineer.

Codex may implement:

* contracts;
* source registry;
* database migrations;
* crawl runs;
* partitions;
* queues;
* checkpoints;
* retry handling;
* snapshot manifests;
* telemetry ledgers;
* offline parsers;
* fixture tests;
* validators;
* source-readiness scoring;
* duplicate-candidate logic;
* review queues;
* dataset batches;
* Docker scaffolding;
* monitoring;
* exports;
* documentation.

Codex must not modify protected acquisition internals.

## 5. Protected paths

The following paths are reserved for Jules-authored protected implementation based on Vuk-approved Gemini blueprints. Vuk controls their application, commits and merges:

```text
src/acquisition/protected/**
src/acquisition/custom_adapter/**
src/acquisition/protected_adapters/**
docker/protected/**
config/protected/**
tests/protected_acquisition/**
```

When one of these paths does not yet exist, its ownership rule still applies.

Codex and ChatGPT must not silently:

* edit;
* delete;
* rename;
* move;
* reformat;
* replace;
* copy its responsibilities elsewhere;
* recreate its internal behavior in another path.

Codex must not directly edit protected paths. Protected defects must be documented and returned as a precise Jules repair prompt. Codex may repair only Codex-owned integration code.

Treat the protected acquisition zone as an opaque implementation of the shared contracts.

## 6. Shared paths

Changes to these paths require explicit approval from Vuk:

```text
src/contracts/**
docs/data-contracts.md
docs/project-boundaries.md
config/schema/**
```

A shared-contract change must include:

* reason for the change;
* compatibility impact;
* migration plan;
* affected adapters;
* affected parsers;
* updated tests;
* updated documentation;
* version increment.

## 7. Codex-safe paths

Unless a task says otherwise, Codex may work in:

```text
src/source_registry/**
src/orchestration/**
src/database/**
src/storage/**
src/parsers/**
src/normalizers/**
src/validators/**
src/dedupe/**
src/quality/**
src/review/**
src/publication/**
src/monitoring/**
src/cli/**
migrations/**
tests/unit/**
tests/integration/**
tests/fixtures/**
scripts/**
docs/**
.github/workflows/**
```

A safe path does not allow Codex to violate the architecture or protected ownership rules.

## 8. Shared contracts

The core shared contracts are:

* `DetailFetchJob`
* `DiscoveryObservation`
* `RawFetchArtifact`
* `FetchTelemetry`
* `ParsedListingCandidate`
* `DatasetBatchManifest`

All contracts must be:

* typed;
* versioned;
* validated at boundaries;
* backwards-compatible when practical;
* documented;
* covered by tests.

## 9. Architecture invariants

These rules may not be violated:

1. Acquisition outputs raw artifacts and telemetry only.
2. Acquisition does not publish into YPI normalized or valuation-ready tables.
3. Parsers do not perform network requests.
4. Parsers preserve source-level values and evidence.
5. Parsers do not perform final YPI canonical mapping.
6. Raw snapshots are immutable.
7. Every snapshot has a path, content hash and acquisition version.
8. Every parser result has a parser version.
9. Every detail job has a reason code.
10. Retries are bounded.
11. One orchestration layer owns job retries and checkpoints.
12. Every discovered listing reaches a known terminal state.
13. Completed work survives a process or container restart.
14. Unknown values remain unknown.
15. No source may block the processing of another source.
16. Every dataset batch has a manifest and checksum.
17. Every record retains source trace.
18. Alternatives do not replace approved components without Vuk’s approval.

## 10. Source identity

Primary source identity is:

```text
source_name + source_listing_key
```

Title and price are change signals, not identity.

If a stable source listing key is unavailable, the fallback identity must:

* be documented;
* be deterministic;
* retain the original URL;
* carry reduced identity confidence;
* be reviewed before Genesis approval.

## 11. Runtime data

Runtime data must not be committed.

Examples:

```text
runtime/
cache.db
*.sqlite
*.sqlite3
checkpoints/
snapshots/
logs/
exports/
backups/
cookies/
session-data/
```

Runtime state belongs on the worker node or approved backup storage.

## 12. Secrets

Never read, print, commit or place in prompts:

* `.env`;
* proxy usernames;
* proxy passwords;
* API keys;
* cookies;
* access tokens;
* private keys;
* browser profiles;
* session material.

Use environment-variable names and safe placeholders.

Logs and exceptions must redact credentials.

`.env.example` may contain variable names only.

## 13. Live request policy

Codex must not perform live requests to production target sources.

Codex tests must use:

* saved fixtures;
* synthetic HTML;
* a local synthetic HTTP server;
* explicitly authorized mock endpoints.

Jules-authored protected live acquisition work, based on Gemini-approved blueprints, remains inside protected paths and Vuk-approved pilot limits.

A live pilot or Genesis run requires Vuk’s explicit approval.

## 14. Orchestration rules

* Use one authoritative queue owner.
* Do not allow two frameworks to independently retry the same job.
* Job insertion must be idempotent.
* Jobs must have leases or equivalent ownership.
* Abandoned processing jobs must be recoverable.
* Retries must have maximum attempt counts.
* Failure reasons must be classified.
* Checkpoints must be persistent.
* Pause and resume must preserve completed work.
* Proxy-byte and disk safety limits must stop work cleanly.

## 15. Snapshot rules

Every raw snapshot record must contain:

* source name;
* source listing key;
* listing URL;
* fetch timestamp;
* acquisition version;
* fetch-method label;
* snapshot path;
* content hash;
* response status;
* artifact status.

Do not overwrite a completed snapshot.

Reprocessing should use existing snapshots before requesting a new live copy.

## 16. Parser rules

Parsers must:

* operate offline;
* preserve raw text;
* return field-level evidence;
* return extraction methods;
* return confidence per field;
* record parser warnings;
* return explicit failure reasons;
* use strict extraction first;
* label fallback extraction as lower confidence;
* return `None` when uncertain.

Parsers must not:

* invent values;
* silently normalize to YPI canonical entities;
* merge cross-source duplicates;
* determine final valuation eligibility;
* calculate valuation scores.

## 17. Testing requirements

Every implementation task must add or update relevant tests.

Minimum tests include:

* contract validation;
* configuration loading;
* database migrations;
* idempotent job insertion;
* retry exhaustion;
* checkpoint resume;
* crash recovery;
* snapshot integrity;
* fixture-based parser regression;
* proxy ledger calculations;
* dataset manifest validation;
* export compatibility;
* backup and restore smoke test.

No live target requests are allowed in CI.

## 18. Docker rules

Use Docker Compose for the current project phase.

Containers must:

* run as non-root;
* use persistent runtime volumes;
* receive secrets only at runtime;
* avoid mounting the Docker socket;
* avoid public ports unless explicitly needed;
* support graceful shutdown;
* preserve queue and snapshots across rebuilds;
* have conservative default resource limits.

Do not introduce Kubernetes without an approved architecture decision.

## 19. Git workflow

Before editing, every agent must:

1. read this file;
2. read relevant documentation;
3. inspect the current tree;
4. list intended file changes;
5. identify whether protected paths are included and confirm that the assigned owner and Vuk have authorized them;
6. identify tests that will be run.

Implementation work should use:

* small feature branches;
* small logical commits;
* descriptive commit messages;
* no unrelated refactors;
* no silent dependency additions.

Do not commit directly to `main` unless Vuk explicitly requests it.

## 20. Documentation rules

Update documentation when changing:

* contracts;
* migrations;
* source registry;
* job states;
* retry behavior;
* parser behavior;
* source scope;
* Genesis rules;
* routine rules;
* exports;
* Docker operation;
* backup or restore procedures.

Source claims must be labelled:

* `observed`
* `hypothesis`
* `verified`
* `deprecated`

## 21. Cross-repository verification

Before every project task, Codex must inspect:

1. the relevant current Scraper Project Second Brain documentation;
2. the relevant current `scraper_project` files, tests, migrations and repository tree;
3. the current implementation step;
4. conflicts between documentation and implementation.

Every Codex response must report:

* Second Brain files checked;
* technical files checked;
* current implementation step;
* architecture alignment;
* documentation conflicts;
* implementation defects;
* strengths;
* weaknesses;
* risks;
* missing evidence;
* protected-code findings;
* whether a Jules repair prompt is required.

Codex must not remove or replace a project idea merely because Codex cannot assist with it.

## 22. Before declaring a task complete

Report:

* files created;
* files modified;
* tests run;
* test results;
* migrations added;
* dependencies added;
* architecture conflicts;
* protected paths checked;
* remaining limitations;
* next recommended task.

A task is not complete when tests fail or architecture boundaries are unclear.

## 23. Genesis restrictions

Do not begin a Genesis scrape until:

* source specification is approved;
* protected adapter validates against contracts;
* fixtures exist;
* offline parser passes;
* staged pilots are reviewed;
* proxy usage is measured;
* stop conditions work;
* resume works;
* Vuk approves execution.

Every discovered listing must finish as:

* `detail_success`
* `list_only_accepted`
* `excluded_with_reason`
* `failed_classified`
* `manual_review`

No discovered listing may disappear from accounting.

## 24. Routine-scrape restrictions

The starting routine is:

* one complete light discovery sweep per source per week;
* conditional detail fetching;
* price-history updates;
* stale-refresh windows;
* missing-listing verification;
* proxy-budget priority degradation;
* versioned delta batches.

Do not deep-fetch every unchanged listing.

## 25. Final rule

When repository evidence conflicts with an assumption, stop and report the conflict.

Never silently change Gemini’s approved acquisition blueprint, Jules’ protected implementation, an experimental project idea or another established project decision.
