"""Consistent SQLite backup and restore helpers."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from database.connection import RuntimeDatabase


def backup_database(database: RuntimeDatabase, destination: Path) -> Path:
    """Create a consistent SQLite backup without overwriting an existing file."""
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"backup destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = database.connect()
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


def restore_database(backup_path: Path, destination: Path) -> Path:
    """Restore a backup into a new destination for explicit, non-destructive recovery tests."""
    backup_path = backup_path.resolve()
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"restore destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(backup_path)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination
