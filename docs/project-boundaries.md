Project Boundaries
Purpose

scraper_project is responsible for acquiring and preparing source-level boat-listing artifacts for YPI.

In scope
source registry;
crawl runs and partitions;
persistent jobs and checkpoints;
protected source adapters;
raw snapshot manifests;
acquisition telemetry;
proxy-usage accounting;
offline source parsers;
parser evidence and confidence;
source-readiness signals;
versioned dataset batches;
YPI raw-ingestion export.

3. docs/project-boundaries.md
Replace the complete Protected acquisition zone section with
Protected acquisition zone

Gemini owns source-specific research and acquisition blueprints.

Jules owns implementation and tests inside:

src/acquisition/protected/**
src/acquisition/custom_adapter/**
src/acquisition/protected_adapters/**
docker/protected/**
config/protected/**
tests/protected_acquisition/**

Vuk applies, commits and merges accepted Jules files or patches.

ChatGPT and Codex may inspect, test and review protected implementation. They must not directly edit, replace, rename, move, reformat or recreate its behaviour.

Protected defects return to Jules through a precise repair prompt.

Experimental tools remain optional until Gemini research, controlled evidence and Vuk approval justify their implementation or promotion.
Replace the stale foundation-status paragraph with
Foundation status

Steps 1–2 are complete.

The repository currently provides typed contracts, source-registry configuration, safe logging, a CLI, Docker scaffolding, versioned SQLite migrations, crawl and partition state, one authoritative detail-job queue, bounded retries, checkpoints, snapshot manifests, parser-run state, proxy accounting, dataset manifests, backup and recovery.

It does not yet contain live protected acquisition adapters, source parsers, Genesis execution or routine scraping.
4. docs/runtime-state.md
Add after the queue-owner paragraph
External acquisition or crawler tools must not create a second authoritative queue, retry system, checkpoint store or terminal-state owner.

Crawlee, Scrapling, browser runtimes and protected source adapters may operate only through the approved source-neutral contracts and orchestration boundary.
5. Create docs/experimental-tools-policy.md

It must contain:

# Experimental Tools Policy

Experimental tools are retained for source-specific research and testing.

Gemini owns research and blueprint decisions.
Jules owns approved protected implementation.
ChatGPT and Codex may review and suggest optimizations.
Vuk approves implementation, rejection, replacement and promotion.

An experimental tool is not implemented merely because it is listed.

An experimental tool is not removed merely because one reviewer cannot assist with it.

Every tool record must include:

- intended source problem;
- source;
- current status;
- maturity;
- Gemini research result;
- approved protected paths;
- Jules implementation version;
- dependency version;
- experiment IDs;
- measured benefits and failures;
- Vuk decision.

Codex-owned source-neutral areas

Codex may work in:

src/contracts/**
src/source_registry/**
src/orchestration/**
src/database/**
src/storage/**
src/parsers/**
src/validators/**
src/quality/**
src/review/**
src/publication/**
src/monitoring/**
src/cli/**
migrations/**
tests/unit/**
tests/integration/**
tests/fixtures/**
docs/**
scripts/**
YPI-owned responsibilities

The scraper project must not become authoritative for:

canonical builder, model or variant mapping;
normalized boat and engine records;
final ownership classification;
cross-source duplicate merging;
final valuation eligibility;
comparable scoring;
valuation range calculations;
the YPI web application.

The scraper exports source-level evidence into YPI raw ingestion.

Live-request boundary

Codex tests use saved fixtures, synthetic HTML or a local test server.

Live source acquisition is performed only through approved Gemini-authored adapters, manually applied and executed under Vuk-approved pilot limits.

Architecture rules
Raw snapshots are immutable.
Parsers perform no network requests.
Unknown values remain unknown.
Retries are bounded.
One orchestration layer owns retries and checkpoints.
Every discovered listing reaches a known terminal state.
No source failure may block another source.
Alternatives never replace approved components without Vuk’s approval.
Secrets and runtime data never enter Git.

## Foundation status

Steps 1–2 are complete.

The repository currently includes:

* typed shared contracts;
* source-registry configuration;
* safe logging and a local CLI;
* Docker scaffolding;
* versioned SQLite migrations;
* crawl-run and partition state;
* one authoritative detail-job queue;
* bounded retries and crash recovery;
* checkpoints and snapshot manifests;
* parser-run state;
* proxy-usage accounting;
* dataset-batch manifests;
* database backup and restore support.

The repository does not yet include:

* live protected acquisition adapters;
* source-specific offline parsers;
* Genesis execution;
* routine scraping.
