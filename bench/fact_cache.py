"""Record/replay cache for the FACT scorer's page fetches.

The FACT scorer re-fetches every cited URL live to check support. Scoring the same
task repeatedly (A/B cells, judge×N) hammers the same hosts -> rate-limiting ->
pages that fetched fine on run 1 return 403/empty on run 4 -> FACT numbers drift.

This cache stores each URL's fetched text on first success and replays it on
subsequent fetches, so a URL is fetched from the live web AT MOST ONCE. Failures are
NOT cached (so a transiently-dead URL can succeed on a later run). Env-gated by the
caller; DB errors degrade to a miss/no-op so the cache can never crash scoring.

Table ``fact_page_cache(url PRIMARY KEY, content, fetched_at)`` in the given SQLite
db (default: the repo's data/cache.db, alongside the retrieval replay cache).
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


class FactFetchCache:
    def __init__(self, db_path: str) -> None:
        self._db = str(db_path)
        try:
            with sqlite3.connect(self._db) as conn:
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS fact_page_cache "
                    "(url TEXT PRIMARY KEY, content TEXT NOT NULL, fetched_at TEXT NOT NULL)"
                )
        except sqlite3.Error:
            pass

    def get(self, url: str) -> str | None:
        try:
            with sqlite3.connect(self._db) as conn:
                row = conn.execute(
                    "SELECT content FROM fact_page_cache WHERE url = ?", (url,)
                ).fetchone()
                return row[0] if row else None
        except sqlite3.Error:
            return None

    def put(self, url: str, content: str) -> None:
        try:
            with sqlite3.connect(self._db) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO fact_page_cache (url, content, fetched_at) "
                    "VALUES (?, ?, ?)",
                    (url, content, datetime.now(UTC).isoformat()),
                )
        except sqlite3.Error:
            pass
