"""Safe runtime-directory and disk-space checks for the isolated worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil


class RuntimeSafetyError(RuntimeError):
    """Raised before work starts when the local runtime is not safe to use."""


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    """The only persistent subdirectories used by the source-neutral worker."""

    root: Path
    database: Path
    checkpoints: Path
    snapshots: Path
    logs: Path
    exports: Path

    @classmethod
    def from_root(cls, root: Path) -> "RuntimePaths":
        resolved = root.resolve()
        return cls(
            root=resolved,
            database=resolved / "database",
            checkpoints=resolved / "checkpoints",
            snapshots=resolved / "snapshots",
            logs=resolved / "logs",
            exports=resolved / "exports",
        )

    def ensure(self) -> None:
        for path in (self.root, self.database, self.checkpoints, self.snapshots, self.logs, self.exports):
            path.mkdir(parents=True, exist_ok=True)


def require_free_space(runtime_root: Path, minimum_free_bytes: int) -> int:
    """Fail before queue work when the approved runtime volume is too full."""
    if isinstance(minimum_free_bytes, bool) or minimum_free_bytes < 0:
        raise ValueError("minimum_free_bytes must be a non-negative integer")
    runtime_root.mkdir(parents=True, exist_ok=True)
    free_bytes = shutil.disk_usage(runtime_root).free
    if free_bytes < minimum_free_bytes:
        raise RuntimeSafetyError(
            f"runtime disk safety stop: {free_bytes} free bytes is below required {minimum_free_bytes}"
        )
    return free_bytes
