"""Versioned SQL migration runner for local runtime databases."""

from __future__ import annotations

from hashlib import sha256
from importlib.resources import files
from importlib.resources.abc import Traversable

from .connection import RuntimeDatabase


class MigrationError(RuntimeError):
    """Raised when a migration is missing or its recorded contents differ."""


def migration_directory() -> Traversable:
    """Return the packaged canonical migration resource directory."""
    return files("database").joinpath("migrations")


def apply_migrations(database: RuntimeDatabase) -> None:
    """Apply each numbered migration exactly once, recording its content hash."""
    with database.write_transaction() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
    paths = sorted(
        (path for path in migration_directory().iterdir() if path.is_file() and path.name[:4].isdigit() and path.name.endswith(".sql")),
        key=lambda path: path.name,
    )
    for path in paths:
        version = path.name.split("_", 1)[0]
        sql = path.read_text(encoding="utf-8")
        checksum = sha256(sql.encode("utf-8")).hexdigest()
        with database.read_connection() as connection:
            applied = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version = ?", (version,)
            ).fetchone()
        if applied is not None:
            if applied["checksum"] != checksum:
                raise MigrationError(f"migration {path.name} has changed after application")
            continue
        with database.write_transaction() as connection:
            # executescript manages its own transaction, so schema and version record survive together.
            connection.executescript(
                "BEGIN IMMEDIATE;\n"
                + sql
                + "\nINSERT INTO schema_migrations(version, checksum, applied_at) VALUES "
                + f"('{version}', '{checksum}', strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));\nCOMMIT;"
            )
