"""Load and validate source registry configuration without making network requests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
import tomllib


class SourceRegistryConfigError(ValueError):
    """Raised when the source registry configuration is invalid."""


_IDENTITY_STRATEGIES = {"stable_source_key", "deterministic_url_fallback"}


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    name: str
    enabled: bool
    identity_strategy: str
    identity_notes: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name or not self.name.replace("_", "").replace("-", "").isalnum():
            raise SourceRegistryConfigError("source name must be non-empty and use letters, digits, _ or -")
        if not isinstance(self.enabled, bool):
            raise SourceRegistryConfigError("enabled must be a boolean")
        if not isinstance(self.identity_strategy, str):
            raise SourceRegistryConfigError("identity_strategy must be a string")
        if self.identity_strategy not in _IDENTITY_STRATEGIES:
            raise SourceRegistryConfigError(f"unsupported identity strategy {self.identity_strategy!r}")
        if self.identity_notes is not None and not isinstance(self.identity_notes, str):
            raise SourceRegistryConfigError("identity_notes must be a string or null")
        if self.identity_strategy == "deterministic_url_fallback" and not self.identity_notes:
            raise SourceRegistryConfigError("deterministic_url_fallback requires identity_notes")


@dataclass(frozen=True, slots=True)
class SourceRegistryConfig:
    registry_version: str
    sources: tuple[SourceDefinition, ...]

    def __post_init__(self) -> None:
        if self.registry_version != "0.1":
            raise SourceRegistryConfigError("unsupported registry_version; expected '0.1'")
        names = [source.name for source in self.sources]
        if len(names) != len(set(names)):
            raise SourceRegistryConfigError("source names must be unique")


def _read_source_definition(value: object) -> SourceDefinition:
    if not isinstance(value, Mapping):
        raise SourceRegistryConfigError("each sources item must be a table")
    allowed = {"name", "enabled", "identity_strategy", "identity_notes"}
    unknown = set(value) - allowed
    if unknown:
        raise SourceRegistryConfigError(f"unsupported source configuration keys: {', '.join(sorted(unknown))}")
    try:
        return SourceDefinition(
            name=value["name"],
            enabled=value["enabled"],
            identity_strategy=value["identity_strategy"],
            identity_notes=value.get("identity_notes"),
        )
    except KeyError as exc:
        raise SourceRegistryConfigError(f"missing required source key {exc.args[0]!r}") from exc


def load_source_registry(path: Path) -> SourceRegistryConfig:
    """Load a local TOML registry; this boundary never opens a network connection."""
    try:
        with path.open("rb") as config_file:
            payload = tomllib.load(config_file)
    except FileNotFoundError as exc:
        raise SourceRegistryConfigError(f"source registry not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise SourceRegistryConfigError(f"invalid TOML source registry: {path}") from exc
    allowed = {"registry_version", "sources"}
    unknown = set(payload) - allowed
    if unknown:
        raise SourceRegistryConfigError(f"unsupported registry keys: {', '.join(sorted(unknown))}")
    if "registry_version" not in payload:
        raise SourceRegistryConfigError("missing required registry_version")
    sources_payload = payload.get("sources", [])
    if not isinstance(sources_payload, list):
        raise SourceRegistryConfigError("sources must be an array of tables")
    return SourceRegistryConfig(
        registry_version=payload["registry_version"],
        sources=tuple(_read_source_definition(source) for source in sources_payload),
    )
