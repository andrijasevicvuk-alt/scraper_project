"""Placeholder-safe CLI. It performs no acquisition or live requests."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from contracts import ContractValidationError, validate_contract_payload
from contracts.models import CONTRACT_TYPES
from source_registry.config import SourceRegistryConfigError, load_source_registry


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
