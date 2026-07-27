"""Shared validation helpers for public contract boundaries."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Any
from urllib.parse import urlparse

CONTRACT_VERSION = "0.1"
_SENSITIVE_KEY_PARTS = ("password", "secret", "token", "cookie", "authorization", "api_key")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractValidationError(ValueError):
    """Raised when a boundary payload violates a shared contract."""


def require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractValidationError(f"{field_name} must be a non-empty string")


def require_utc_timestamp(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractValidationError(f"{field_name} must be a timezone-aware UTC timestamp")
    if value.utcoffset().total_seconds() != 0:
        raise ContractValidationError(f"{field_name} must use UTC")


def require_http_url(value: str, field_name: str) -> None:
    require_text(value, field_name)
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ContractValidationError(f"{field_name} must be an absolute HTTP(S) URL")


def require_contract_version(value: str) -> None:
    require_text(value, "contract_version")
    major = value.split(".", 1)[0]
    supported_major = CONTRACT_VERSION.split(".", 1)[0]
    if major != supported_major:
        raise ContractValidationError(
            f"unsupported contract major version {major!r}; supported major is {supported_major!r}"
        )


def require_sha256(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ContractValidationError(f"{field_name} must be a lowercase SHA-256 hex digest")


def require_non_negative_int(value: int, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractValidationError(f"{field_name} must be a non-negative integer")


def reject_sensitive_keys(value: Any, field_name: str = "payload") -> None:
    """Prevent credentials and session material from entering extensible mappings."""
    if isinstance(value, Mapping):
        for key, nested_value in value.items():
            key_text = str(key).lower()
            if any(part in key_text for part in _SENSITIVE_KEY_PARTS):
                raise ContractValidationError(f"{field_name} must not contain sensitive key {key!r}")
            reject_sensitive_keys(nested_value, f"{field_name}.{key}")
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_sensitive_keys(item, field_name)


def parse_utc_timestamp(value: object, field_name: str) -> datetime:
    if not isinstance(value, str):
        raise ContractValidationError(f"{field_name} must be an ISO-8601 timestamp string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractValidationError(f"{field_name} must be an ISO-8601 timestamp string") from exc
    require_utc_timestamp(parsed, field_name)
    return parsed


def validate_contract_payload(contract_name: str, payload: Mapping[str, object]) -> object:
    """Instantiate and validate a supported contract from an untrusted mapping."""
    from .models import CONTRACT_TYPES

    contract_type = CONTRACT_TYPES.get(contract_name)
    if contract_type is None:
        supported = ", ".join(sorted(CONTRACT_TYPES))
        raise ContractValidationError(f"unknown contract {contract_name!r}; supported: {supported}")
    if not isinstance(payload, Mapping):
        raise ContractValidationError("contract payload must be an object")
    try:
        return contract_type.from_mapping(payload)
    except TypeError as exc:
        raise ContractValidationError(f"invalid {contract_name} payload shape: {exc}") from exc
