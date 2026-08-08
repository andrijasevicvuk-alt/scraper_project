# Project Boundaries

## Purpose

`scraper_project` acquires and prepares source-level boat-listing artifacts for YPI. It owns source registry state, crawl state, immutable raw snapshots, acquisition telemetry, offline parser outputs, source-readiness signals, dataset manifests, and controlled YPI raw-ingestion exports.

## Protected acquisition zone

Gemini owns source research, acquisition blueprints, experiments, and source documentation.

Jules owns protected source-specific implementation and tests in:

```text
src/acquisition/protected/**
src/acquisition/custom_adapter/**
src/acquisition/protected_adapters/**
docker/protected/**
config/protected/**
tests/protected_acquisition/**
```

Vuk applies, commits, and merges accepted protected changes. ChatGPT and Codex may inspect, test, and review protected implementation, but must not directly edit, replace, rename, move, reformat, or recreate it. A protected defect must be returned as a precise Jules repair prompt.

Experimental acquisition tools remain available for Gemini research and Jules implementation only after Vuk approval. They are not added, removed, or replaced by Codex during source-neutral work.

## Codex-owned source-neutral areas

Codex may work in the source registry, orchestration, database, storage, offline parser, validation, quality, review, publication, monitoring, CLI, tests, Docker scaffold, CI, scripts, and documentation, subject to the shared-contract approval boundary.

## YPI-owned responsibilities

The scraper is not authoritative for canonical builder/model/variant mapping, normalized boat or engine records, final ownership classification, cross-source duplicate merging, valuation eligibility, comparable scoring, valuation ranges, or the YPI web application. It exports source-level evidence to YPI raw ingestion only.

## Live-request boundary

Codex uses saved fixtures, synthetic HTML, or a local synthetic server. Jules-authored protected live acquisition, based on Gemini blueprints, runs only under Vuk-approved pilot limits.

## Foundation status

Steps 1-2 are complete. The repository has typed contracts, source registry configuration, local CLI and logging, Docker scaffolding, versioned SQLite state, authoritative queueing, bounded retries, checkpoints, immutable snapshot manifests, parser-run state, proxy accounting, dataset manifests, and backup/restore support.

Step 3A adds a source-neutral synthetic worker and isolated Docker validation. It does not add live protected adapters, source parsers, Genesis execution, routine scraping, or YPI business logic.
