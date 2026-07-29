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
Protected acquisition zone

Gemini authors source-specific code for:

src/acquisition/protected/**
src/acquisition/custom_adapter/**
src/acquisition/protected_adapters/**
docker/protected/**
config/protected/**
tests/protected_acquisition/**

Codex must not silently edit, replace, move, rename or recreate the responsibilities of these paths. A narrow integration correction requires Vuk’s explicit approval.

Protected implementations communicate with the rest of the system only through shared contracts.

The protected directories are reserved for Gemini-authored acquisition code. Gemini returns proposed files or patches; Vuk controls their application and commits. Codex does not create competing implementations in other paths.

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

Foundation status

The initial source-neutral foundation provides typed contracts, a local source-registry configuration boundary, safe logging, a placeholder-safe CLI and Docker development scaffold. It does not implement live acquisition, protected adapters, queues, retries, parsers, Genesis, routine scraping, canonical YPI mapping, cross-source deduplication, eligibility or valuation logic.
