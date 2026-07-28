"""Placeholder-safe CLI. It performs no acquisition or live requests."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
from uuid import uuid4

from contracts import ContractValidationError, validate_contract_payload
from contracts.models import CONTRACT_VERSION, DetailFetchJob, DetailReasonCode, DiscoveryObservation
from contracts.models import CONTRACT_TYPES
from database import RuntimeDatabase, RuntimeRepositories
from orchestration import DetailFetchQueue
from source_registry.config import SourceRegistryConfigError, load_source_registry
from storage import backup_database


def _runtime_repositories(database_path: Path) -> RuntimeRepositories:
    return RuntimeRepositories(RuntimeDatabase(database_path))


def _source_list(args: argparse.Namespace) -> int:
    try:
        registry = load_source_registry(args.config)
    except SourceRegistryConfigError as exc:
        print(f"source registry error: {exc}", file=sys.stderr)
        return 2
    for source in registry.sources:
        state = "enabled" if source.enabled else "disabled"
        print(f"{source.name}\t{state}\t{source.identity_strategy}")
    return 0


def _contract_validate(args: argparse.Namespace) -> int:
    if args.contract is None or args.input is None:
        print("Supported contracts: " + ", ".join(sorted(CONTRACT_TYPES)))
        print("Use --contract NAME --input PATH to validate a local JSON payload.")
        return 0
    try:
        with args.input.open(encoding="utf-8") as payload_file:
            payload = json.load(payload_file)
        validate_contract_payload(args.contract, payload)
    except (OSError, json.JSONDecodeError, ContractValidationError) as exc:
        print(f"contract validation error: {exc}", file=sys.stderr)
        return 2
    print(f"{args.contract}: valid")
    return 0


def _health(_: argparse.Namespace) -> int:
    print("ok: source-neutral foundation; live acquisition is not implemented")
    return 0


def _runtime_fixture_crawl(args: argparse.Namespace) -> int:
    repositories = _runtime_repositories(args.database)
    source_name = "fixture_source"
    crawl_run_id = str(uuid4())
    partition_id = str(uuid4())
    listing_key = "fixture-listing-001"
    now = datetime.now(UTC)
    repositories.sources.upsert(source_name, False, "stable_source_key", "Synthetic local fixture only.")
    repositories.crawls.create_run(crawl_run_id, source_name)
    repositories.crawls.start(crawl_run_id)
    repositories.crawls.create_partition(partition_id, crawl_run_id, source_name, "fixture-page-1")
    repositories.observations.append(
        DiscoveryObservation(
            contract_version=CONTRACT_VERSION,
            crawl_run_id=crawl_run_id,
            source_name=source_name,
            source_listing_key=listing_key,
            listing_url="https://example.invalid/fixture-listing-001",
            observed_at=now,
            visible_title="Synthetic fixture boat",
            visible_price_text=None,
            visible_currency=None,
            visible_specs={},
            visible_status="observed",
            card_fingerprint="fixture-card-v1",
            discovery_partition="fixture-page-1",
        )
    )
    job_id = repositories.jobs.create_idempotent(
        DetailFetchJob(
            contract_version=CONTRACT_VERSION,
            job_id=str(uuid4()),
            crawl_run_id=crawl_run_id,
            source_name=source_name,
            source_listing_key=listing_key,
            listing_url="https://example.invalid/fixture-listing-001",
            reason_code=DetailReasonCode.NEW_LISTING,
            priority=0,
            attempt_number=1,
            max_attempts=3,
            scheduled_at=now,
            metadata={"fixture": "synthetic"},
        )
    )
    repositories.checkpoints.save(crawl_run_id, partition_id, "fixture-page-1")
    print(json.dumps({"crawl_run_id": crawl_run_id, "partition_id": partition_id, "job_id": job_id}, sort_keys=True))
    return 0


def _runtime_queue_status(args: argparse.Namespace) -> int:
    print(json.dumps(_runtime_repositories(args.database).jobs.status_counts(), sort_keys=True))
    return 0


def _runtime_recover_abandoned(args: argparse.Namespace) -> int:
    database = RuntimeDatabase(args.database)
    RuntimeRepositories(database)
    print(json.dumps(DetailFetchQueue(database).recover_abandoned(), sort_keys=True))
    return 0


def _runtime_proxy_usage(args: argparse.Namespace) -> int:
    print(json.dumps(_runtime_repositories(args.database).proxy_usage.totals(), sort_keys=True))
    return 0


def _runtime_backup(args: argparse.Namespace) -> int:
    database = RuntimeDatabase(args.database)
    RuntimeRepositories(database)
    print(backup_database(database, args.destination))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="scraper", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    source = commands.add_parser("source", help="inspect local source-registry configuration")
    source_commands = source.add_subparsers(dest="source_command", required=True)
    source_list = source_commands.add_parser("list", help="list configured sources")
    source_list.add_argument("--config", type=Path, default=Path("config/sources.example.toml"))
    source_list.set_defaults(handler=_source_list)

    contract = commands.add_parser("contract", help="validate local shared-contract payloads")
    contract_commands = contract.add_subparsers(dest="contract_command", required=True)
    validate = contract_commands.add_parser("validate", help="validate a local JSON payload")
    validate.add_argument("--contract", choices=sorted(CONTRACT_TYPES))
    validate.add_argument("--input", type=Path)
    validate.set_defaults(handler=_contract_validate)

    health = commands.add_parser("health", help="report local scaffold health")
    health.set_defaults(handler=_health)

    runtime = commands.add_parser("runtime", help="inspect synthetic local SQLite runtime state")
    runtime_commands = runtime.add_subparsers(dest="runtime_command", required=True)

    fixture_crawl = runtime_commands.add_parser("fixture-crawl", help="create a synthetic crawl run, observation, job and checkpoint")
    fixture_crawl.add_argument("--database", type=Path, default=Path("runtime/scraper.sqlite"))
    fixture_crawl.set_defaults(handler=_runtime_fixture_crawl)

    queue_status = runtime_commands.add_parser("queue-status", help="show persisted detail-fetch job states")
    queue_status.add_argument("--database", type=Path, default=Path("runtime/scraper.sqlite"))
    queue_status.set_defaults(handler=_runtime_queue_status)

    recover = runtime_commands.add_parser("recover-abandoned", help="recover expired processing leases with bounded retries")
    recover.add_argument("--database", type=Path, default=Path("runtime/scraper.sqlite"))
    recover.set_defaults(handler=_runtime_recover_abandoned)

    proxy_usage = runtime_commands.add_parser("proxy-usage", help="show persisted proxy byte totals")
    proxy_usage.add_argument("--database", type=Path, default=Path("runtime/scraper.sqlite"))
    proxy_usage.set_defaults(handler=_runtime_proxy_usage)

    backup = runtime_commands.add_parser("backup", help="create a non-overwriting SQLite runtime backup")
    backup.add_argument("--database", type=Path, default=Path("runtime/scraper.sqlite"))
    backup.add_argument("--destination", type=Path, required=True)
    backup.set_defaults(handler=_runtime_backup)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
