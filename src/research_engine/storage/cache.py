"""SQLite-backed cache for discovered source records.

Stores `Paper`-shaped results per query and provider so repeated discovery
runs can avoid duplicate upstream calls.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from research_engine.discovery.schema import Paper


@dataclass(frozen=True, slots=True)
class CachedSearchResult:
    """One cached search result entry."""

    query: str
    source: str
    paper: Paper
    cached_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class SourceCache:
    """Persistent cache for raw discovery results."""

    MIGRATIONS: tuple[str, ...] = (
        """
        CREATE TABLE IF NOT EXISTS source_cache (
            cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            source TEXT NOT NULL,
            paper_key TEXT NOT NULL,
            paper_json TEXT NOT NULL,
            cached_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_source_cache_query ON source_cache(query);
        CREATE INDEX IF NOT EXISTS idx_source_cache_source ON source_cache(source);
        CREATE INDEX IF NOT EXISTS idx_source_cache_key ON source_cache(paper_key);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_source_cache_unique
        ON source_cache(query, source, paper_key);
        """,
    )

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            for migration in self.MIGRATIONS:
                conn.executescript(migration)
            conn.commit()
        finally:
            conn.close()

    def put(self, query: str, source: str, papers: list[Paper]) -> int:
        """Store papers for a query/source pair. Returns number of rows inserted."""
        now = datetime.now(UTC).isoformat()
        rows = [
            (query, source, paper.key, json.dumps(paper.to_dict(), default=str), now)
            for paper in papers
        ]
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executemany(
                """
                INSERT OR REPLACE INTO source_cache (query, source, paper_key, paper_json, cached_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def get(self, query: str, source: str | None = None) -> list[CachedSearchResult]:
        """Return cached results for a query, optionally filtered by source."""
        sql = "SELECT * FROM source_cache WHERE query = ?"
        params: list[Any] = [query]
        if source is not None:
            sql += " AND source = ?"
            params.append(source)
        sql += " ORDER BY cached_at DESC"

        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        results: list[CachedSearchResult] = []
        for row in rows:
            try:
                paper = Paper.from_dict(json.loads(row["paper_json"]))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            results.append(
                CachedSearchResult(
                    query=row["query"],
                    source=row["source"],
                    paper=paper,
                    cached_at=datetime.fromisoformat(row["cached_at"]),
                )
            )
        return results

    def get_papers(self, query: str, source: str | None = None) -> list[Paper]:
        """Convenience accessor returning only the cached Paper objects."""
        return [r.paper for r in self.get(query, source)]

    def has(self, query: str, source: str | None = None) -> bool:
        """Return True if any cached entry exists for the query/source."""
        sql = "SELECT 1 FROM source_cache WHERE query = ?"
        params: list[Any] = [query]
        if source is not None:
            sql += " AND source = ?"
            params.append(source)
        sql += " LIMIT 1"
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(sql, params).fetchone()
        finally:
            conn.close()
        return row is not None

    def clear(self) -> int:
        """Remove all cached entries. Returns number of rows deleted."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute("DELETE FROM source_cache")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
