"""Campaign cleanup: deduplicate files and vacuum SQLite DBs."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from research_engine.cleanup.dedup_files import FileDeduplicator


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Outcome of a cleanup run."""

    ok: bool
    vacuumed_db: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class CleanupJanitor:
    """Lightweight cleanup that deduplicates files and compacts SQLite DBs."""

    def __init__(
        self,
        state_db_path: Path | str | None = None,
        engine_data_dir: Path | str | None = None,
        project_root: Path | str | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve() if project_root else None
        self.state_db_path = Path(state_db_path) if state_db_path else None
        self.engine_data_dir = Path(engine_data_dir) if engine_data_dir else None

    def _contained(self, path: Path | None) -> tuple[bool, str]:
        """Return (ok, reason) when ``path`` must live under project_root."""
        if path is None:
            return True, "no path"
        if self.project_root is None:
            return True, "no containment root configured"
        try:
            resolved = path.resolve()
        except OSError as exc:
            return False, f"cannot resolve {path}: {exc}"
        if resolved.is_relative_to(self.project_root):
            return True, "contained"
        return False, f"{resolved} is outside project root {self.project_root}"

    def clean(self) -> CleanupResult:
        """Deduplicate files under ``engine_data_dir`` and vacuum the state DB.

        Research folders and campaign briefs are intentionally left intact.
        """
        for label, path in (
            ("state_db", self.state_db_path),
            ("engine_data_dir", self.engine_data_dir),
        ):
            ok, reason = self._contained(path)
            if not ok:
                return CleanupResult(ok=False, error=f"{label} containment failed: {reason}")

        dedup_meta: dict[str, Any] = {}
        if self.engine_data_dir is not None:
            dedup = FileDeduplicator(self.engine_data_dir)
            dedup_result = dedup.dedup()
            dedup_meta = {
                "dedup_scanned": dedup_result.scanned,
                "dedup_removed": dedup_result.duplicates_removed,
                "dedup_bytes_saved": dedup_result.bytes_saved,
                "dedup_error": dedup_result.error,
            }
            if not dedup_result.ok:
                return CleanupResult(
                    ok=False,
                    error=dedup_result.error,
                    meta=dedup_meta,
                )

        if self.state_db_path is None:
            return CleanupResult(
                ok=True,
                error="No state DB configured; nothing to vacuum",
                meta=dedup_meta,
            )
        if not self.state_db_path.exists():
            return CleanupResult(
                ok=False,
                error=f"State DB not found: {self.state_db_path}",
                meta=dedup_meta,
            )
        try:
            conn = sqlite3.connect(self.state_db_path)
            try:
                conn.execute("VACUUM")
                conn.commit()
            finally:
                conn.close()
            return CleanupResult(
                ok=True,
                vacuumed_db=str(self.state_db_path),
                meta={
                    "size_after_bytes": self.state_db_path.stat().st_size,
                    **dedup_meta,
                },
            )
        except sqlite3.Error as exc:
            return CleanupResult(
                ok=False,
                error=f"Vacuum failed: {exc}",
                meta=dedup_meta,
            )
