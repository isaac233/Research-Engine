"""File-level deduplication for the engine's data/ directory."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DedupResult:
    """Outcome of a file deduplication run."""

    ok: bool
    scanned: int = 0
    duplicates_removed: int = 0
    bytes_saved: int = 0
    removed_paths: list[str] = field(default_factory=list)
    error: str | None = None


class FileDeduplicator:
    """Remove duplicate files under a directory while keeping one copy each."""

    def __init__(self, root: Path | str, *, min_size_bytes: int = 0) -> None:
        self.root = Path(root)
        self.min_size_bytes = min_size_bytes

    def dedup(self) -> DedupResult:
        """Scan ``root`` and remove duplicate files by content hash.

        For every unique file content, the first encountered path is kept
        and any subsequent duplicates are deleted. Empty files and files
        smaller than ``min_size_bytes`` are ignored.
        """
        if not self.root.exists():
            return DedupResult(ok=True, error=f"Root does not exist: {self.root}")

        seen: dict[str, Path] = {}
        removed: list[Path] = []
        bytes_saved = 0
        scanned = 0

        root_resolved = self.root.resolve()
        try:
            for dirpath, _dirnames, filenames in os.walk(self.root, followlinks=False):
                dir_path = Path(dirpath).resolve()
                if not dir_path.is_relative_to(root_resolved):
                    continue
                for filename in filenames:
                    path = dir_path / filename
                    if path.is_symlink():
                        continue
                    if not path.is_file():
                        continue
                    # Re-check containment on the real path to avoid symlink races.
                    try:
                        real_path = path.resolve()
                    except OSError:
                        continue
                    if not real_path.is_relative_to(root_resolved):
                        continue
                    scanned += 1
                    try:
                        size = path.stat().st_size
                    except OSError:
                        continue
                    if size < self.min_size_bytes:
                        continue

                    file_hash = self._hash_file(path)
                    if file_hash is None:
                        continue

                    if file_hash in seen:
                        try:
                            bytes_saved += size
                            os.remove(path)
                            removed.append(path)
                        except OSError:
                            continue
                    else:
                        seen[file_hash] = path
        except OSError as exc:
            return DedupResult(
                ok=False,
                scanned=scanned,
                duplicates_removed=len(removed),
                bytes_saved=bytes_saved,
                removed_paths=[str(p) for p in removed],
                error=f"Dedup failed: {exc}",
            )

        return DedupResult(
            ok=True,
            scanned=scanned,
            duplicates_removed=len(removed),
            bytes_saved=bytes_saved,
            removed_paths=[str(p) for p in removed],
        )

    def _hash_file(self, path: Path) -> str | None:
        """Return SHA-256 hex digest of a file, or None on read failure.

        Uses ``O_NOFOLLOW`` on platforms that support it so a symlink swapped
        in after the lstat check cannot be dereferenced.
        """
        hasher = hashlib.sha256()
        try:
            if hasattr(os, "O_NOFOLLOW"):
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                try:
                    with os.fdopen(fd, "rb", closefd=True) as fh:
                        while True:
                            chunk = fh.read(8192)
                            if not chunk:
                                break
                            hasher.update(chunk)
                except Exception:  # noqa: BLE001
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    return None
            else:
                with path.open("rb") as fh:
                    while True:
                        chunk = fh.read(8192)
                        if not chunk:
                            break
                        hasher.update(chunk)
        except OSError:
            return None
        return hasher.hexdigest()
