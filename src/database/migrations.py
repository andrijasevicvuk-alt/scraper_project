"""Versioned SQL migration runner for local runtime databases."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from .connection import RuntimeDatabase


class MigrationError(RuntimeError):
    """Raised when a migration is missing or its recorded contents differ."""


def migration_directory() -> Path:
    return Path(__file__).resolve().parents[2] / "migrations"


def apply_migrations(database: RuntimeDatabase) -> None:
    """Apply each numbered migration exactly once, recording its content hash."""
    with database.write_transaction() as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL)"
        )
    for path in sorted(migration_directory().glob("[0-9][0-9][0-9][0-9]_*.sql")):
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
