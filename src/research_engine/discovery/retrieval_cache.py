"""Record-then-replay cache for the ReAct retrieval layer (determinism).

The react loop hits serp (SearXNG) and fetches pages LIVE every run. SearXNG returns a
different result set/ordering each call and live reads flip between 200/403, so the same
config banks different evidence run-to-run — measured ~±11 RACE variance on task 53, which
makes config-vs-config comparison unreliable (you tune against noise).

This cache records, on first encounter, each serp query's ordered result list AND each
page's fetched text, then replays them verbatim thereafter. With the react LLM calls already
at temperature 0, a re-run of the same config re-issues the same queries → replays the same
URLs → replays the same page text → banks identical evidence. Retrieval variance collapses to
judge noise (~±2). Different configs that issue new queries record those live on first use and
replay them after, so shared queries stay held constant across configs (isolating the config's
effect from serp luck).

Empty results are cached too (a query that found nothing / a read that 403'd and CDP couldn't
recover), so they aren't re-attempted live each run — that emptiness is part of the recording.

Persisted in ``data/cache.db`` (own tables; additive, no conflict with ``SourceCache``).
Env-gated: unset ``RESEARCH_ENGINE_RETRIEVAL_CACHE`` = live behavior, byte-identical. Delete the
two tables (or the flag) to force a fresh recording.

KNOWN LIMITATION (follow-up): the serp key is the *refined query*, produced by an LLM call
(``refine_query``) that is not itself cached. At temperature 0 that query is usually stable, but
Ollama is not bit-deterministic, so an occasional token drift yields a fresh key → a live serp
fetch for that objective (variance leaks back in for that one query). The complete fix is to
record-then-replay the reasoning calls too (objectives / refine / summarize / outline), keyed by a
hash of their inputs — same pattern, next increment. The writer/deepen/abstain calls (post-plan,
also temp 0) remain a small residual variance; for writer-side comparisons use the bounded cache
A/B (``bench/writer_eval``) instead. This cache collapses the dominant serp+page-fetch variance.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research_engine.discovery.schema import Paper

_SCHEMA = """
CREATE TABLE IF NOT EXISTS serp_replay_cache (
    query       TEXT PRIMARY KEY,
    papers_json TEXT NOT NULL,
    cached_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS page_replay_cache (
    url       TEXT PRIMARY KEY,
    text      TEXT NOT NULL,
    cached_at TEXT NOT NULL
);
"""


class RetrievalCache:
    """Persistent record-then-replay of serp results (by query) and page text (by url)."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript(_SCHEMA)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def get_serp(self, query: str) -> list[Paper] | None:
        """Replay a query's ordered papers; None on miss (distinct from a cached empty list).

        Any DB/parse error is treated as a miss (returns None) so the caller falls through to a
        live fetch — a lock/IO hiccup must degrade to the noisy-but-working live path, never
        crash the task (the live path it sits beside is deliberately non-fatal too).
        """
        row = self._read("SELECT papers_json FROM serp_replay_cache WHERE query = ?", query)
        if row is None:
            return None
        try:
            data = json.loads(row)
        except (json.JSONDecodeError, ValueError):
            return None
        return [Paper.from_dict(d) for d in data if isinstance(d, dict)]

    def put_serp(self, query: str, papers: list[Paper]) -> None:
        """Record a query's ordered result list (order preserved for reproducible reads)."""
        blob = json.dumps([p.to_dict() for p in papers], default=str)
        self._write("serp_replay_cache", "query", query, "papers_json", blob)

    def get_page(self, url: str) -> str | None:
        """Replay a url's fetched text; None on miss (distinct from a cached empty string).

        DB errors degrade to a miss (→ live fetch), never a crash — see ``get_serp``.
        """
        row = self._read("SELECT text FROM page_replay_cache WHERE url = ?", url)
        return None if row is None else str(row)

    def put_page(self, url: str, text: str) -> None:
        """Record a url's fetched text (including "" for a dry/blocked read)."""
        self._write("page_replay_cache", "url", url, "text", text)

    def _read(self, sql: str, key: str) -> str | None:
        """Run a single-value lookup; None on miss OR any DB error (degrade, never crash)."""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                row = conn.execute(sql, (key,)).fetchone()
            finally:
                conn.close()
        except sqlite3.Error:  # lock/IO/corruption → treat as a miss, fall through to live
            return None
        return None if row is None else row[0]

    def _write(self, table: str, key_col: str, key: str, val_col: str, val: str) -> None:
        """Record a row; any DB error is swallowed (a failed cache write must not abort a run)."""
        try:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    f"INSERT OR REPLACE INTO {table} ({key_col}, {val_col}, cached_at) "  # noqa: S608 — table/cols are internal literals, never user input
                    f"VALUES (?, ?, ?)",
                    (key, val, self._now()),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:  # lock/IO → skip caching this call, keep the run alive
            pass
