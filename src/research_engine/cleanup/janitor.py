"""Campaign cleanup: vacuum state DB without deleting research artifacts."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """Outcome of a cleanup run."""

    ok: bool
    vacuumed_db: str | None = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class CleanupJanitor:
    """Lightweight cleanup that compacts the SQLite state DB."""

    def __init__(self, state_db_path: Path | str | None = None) -> None:
        self.state_db_path = Path(state_db_path) if state_db_path else None

    def clean(self) -> CleanupResult:
        """Vacuum the state DB and return a receipt.

        Research folders and campaign briefs are intentionally left intact.
        """
        if self.state_db_path is None:
            return CleanupResult(ok=True, error="No state DB configured; nothing to vacuum")
        if not self.state_db_path.exists():
            return CleanupResult(
                ok=False,
                error=f"State DB not found: {self.state_db_path}",
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
                meta={"size_after_bytes": self.state_db_path.stat().st_size},
            )
        except sqlite3.Error as exc:
            return CleanupResult(
                ok=False,
                error=f"Vacuum failed: {exc}",
            )
