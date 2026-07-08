"""Persistent knowledge base of useful sources discovered by agents.

Stores a searchable catalog of sources, what information they provide, how to
access them, and qualitative notes so future campaigns can reuse known-good
sources instead of rediscovering them from scratch.
"""

from __future__ import annotations

import json
import sqlite3
import urllib.parse
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from research_engine.storage._redaction import (
    redact_meta,
    redact_secrets,
    redact_url,
    sanitize_fts_query,
)


@dataclass(frozen=True, slots=True)
class SourceMemoryEntry:
    """Immutable snapshot of a remembered source.

    Designed to be self-describing for agnostic AI review: every field is
    human-readable and every list/dict is JSON-serializable.
    """

    source_id: str
    canonical_url: str
    host: str
    source_type: str
    information_types: list[str] = field(default_factory=list)
    topic_tags: list[str] = field(default_factory=list)
    access_method: str = ""
    requires_auth: bool = False
    rate_limit_notes: str = ""
    reliability_score: float = 0.5
    quality_notes: str = ""
    search_hints: dict[str, Any] = field(default_factory=dict)
    example_keys: list[str] = field(default_factory=list)
    example_urls: list[str] = field(default_factory=list)
    last_seen_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    discovery_campaign_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for AI review and export."""
        return {
            "source_id": self.source_id,
            "canonical_url": self.canonical_url,
            "host": self.host,
            "source_type": self.source_type,
            "information_types": list(self.information_types),
            "topic_tags": list(self.topic_tags),
            "access_method": self.access_method,
            "requires_auth": self.requires_auth,
            "rate_limit_notes": self.rate_limit_notes,
            "reliability_score": self.reliability_score,
            "quality_notes": self.quality_notes,
            "search_hints": dict(self.search_hints),
            "example_keys": list(self.example_keys),
            "example_urls": list(self.example_urls),
            "last_seen_at": self.last_seen_at.isoformat(),
            "discovery_campaign_id": self.discovery_campaign_id,
            "meta": dict(self.meta),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class SourceMemory:
    """SQLite-backed, full-text-searchable catalog of useful sources.

    The schema is intentionally denormalized for readability and search, with
    companion tag tables to support efficient topic/information-type filtering.
    An explicit INTEGER PRIMARY KEY is used as the FTS5 content rowid so rowids
    stay stable across VACUUM.
    """

    MIGRATIONS: tuple[str, ...] = (
        """
        CREATE TABLE IF NOT EXISTS source_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id TEXT NOT NULL UNIQUE,
            canonical_url TEXT NOT NULL,
            host TEXT NOT NULL,
            source_type TEXT NOT NULL,
            access_method TEXT NOT NULL DEFAULT '',
            requires_auth INTEGER NOT NULL DEFAULT 0,
            rate_limit_notes TEXT NOT NULL DEFAULT '',
            reliability_score REAL NOT NULL DEFAULT 0.5,
            quality_notes TEXT NOT NULL DEFAULT '',
            search_hints TEXT NOT NULL DEFAULT '{}',
            example_keys TEXT NOT NULL DEFAULT '[]',
            example_urls TEXT NOT NULL DEFAULT '[]',
            last_seen_at TEXT NOT NULL,
            discovery_campaign_id TEXT,
            meta TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_source_memory_host ON source_memory(host);
        CREATE INDEX IF NOT EXISTS idx_source_memory_type ON source_memory(source_type);
        CREATE INDEX IF NOT EXISTS idx_source_memory_reliability ON source_memory(reliability_score);
        CREATE INDEX IF NOT EXISTS idx_source_memory_last_seen ON source_memory(last_seen_at);
        CREATE INDEX IF NOT EXISTS idx_source_memory_campaign ON source_memory(discovery_campaign_id);
        """,
        """
        CREATE TABLE IF NOT EXISTS source_memory_tags (
            source_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            tag_kind TEXT NOT NULL DEFAULT 'topic',
            FOREIGN KEY (source_id) REFERENCES source_memory(source_id) ON DELETE CASCADE,
            PRIMARY KEY (source_id, tag, tag_kind)
        );
        CREATE INDEX IF NOT EXISTS idx_source_memory_tags_tag ON source_memory_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_source_memory_tags_kind ON source_memory_tags(tag_kind);
        """,
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS source_memory_fts USING fts5(
            source_id,
            canonical_url,
            host,
            source_type,
            access_method,
            rate_limit_notes,
            quality_notes,
            search_hints,
            information_types,
            topic_tags,
            content='',
            content_rowid='id'
        );
        """,
    )

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        """Return a connection with foreign-key enforcement enabled."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def _ensure_schema(self) -> None:
        conn = self._connect()
        try:
            for migration in self.MIGRATIONS:
                conn.executescript(migration)
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def _canonical_source_id(url: str) -> str:
        """Create a stable source id from a URL.

        Normalizes scheme, host, and path so minor query variations do not
        fragment the memory.
        """
        try:
            parsed = urllib.parse.urlparse(url)
            host = (parsed.hostname or "").lower()
            path = parsed.path.rstrip("/")
            return f"{parsed.scheme}://{host}{path}".lower()
        except ValueError:
            return url.lower().strip()

    @staticmethod
    def _extract_host(url: str) -> str:
        try:
            return (urllib.parse.urlparse(url).hostname or "").lower()
        except ValueError:
            return ""

    def _normalize_inputs(
        self,
        canonical_url: str,
        source_type: str,
        information_types: list[str] | None,
        topic_tags: list[str] | None,
        access_method: str,
        requires_auth: bool,
        rate_limit_notes: str,
        reliability_score: float,
        quality_notes: str,
        search_hints: dict[str, Any] | None,
        example_keys: list[str] | None,
        example_urls: list[str] | None,
        discovery_campaign_id: str | None,
        meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Redact and normalize all incoming fields."""
        canonical_url = redact_url(canonical_url)
        scheme = urllib.parse.urlparse(canonical_url).scheme
        if scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported URL scheme for source memory: {scheme!r}")
        return {
            "source_id": self._canonical_source_id(canonical_url),
            "canonical_url": canonical_url,
            "host": self._extract_host(canonical_url),
            "source_type": source_type,
            "information_types": sorted(set(information_types or [])),
            "topic_tags": sorted(set(topic_tags or [])),
            "access_method": redact_secrets(access_method),
            "requires_auth": requires_auth,
            "rate_limit_notes": redact_secrets(rate_limit_notes),
            "reliability_score": max(0.0, min(1.0, reliability_score)),
            "quality_notes": redact_secrets(quality_notes),
            "search_hints": redact_meta(search_hints or {}),
            "example_keys": example_keys or [],
            "example_urls": [redact_url(url) for url in (example_urls or [])],
            "discovery_campaign_id": discovery_campaign_id,
            "meta": redact_meta(meta or {}),
        }

    def remember(
        self,
        canonical_url: str,
        source_type: str,
        information_types: list[str] | None = None,
        topic_tags: list[str] | None = None,
        access_method: str = "",
        requires_auth: bool = False,
        rate_limit_notes: str = "",
        reliability_score: float = 0.5,
        quality_notes: str = "",
        search_hints: dict[str, Any] | None = None,
        example_keys: list[str] | None = None,
        example_urls: list[str] | None = None,
        discovery_campaign_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> SourceMemoryEntry:
        """Upsert a source into memory and return the resulting entry."""
        now = datetime.now(UTC)
        v = self._normalize_inputs(
            canonical_url,
            source_type,
            information_types,
            topic_tags,
            access_method,
            requires_auth,
            rate_limit_notes,
            reliability_score,
            quality_notes,
            search_hints,
            example_keys,
            example_urls,
            discovery_campaign_id,
            meta,
        )

        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            existing = self._load_existing(conn, v["source_id"])
            source_pk = existing["id"] if existing else None
            created_at = (
                datetime.fromisoformat(existing["created_at"]) if existing else now
            )

            source_pk = self._insert_source(conn, v, source_pk, created_at, now)
            self._refresh_tags(conn, v)
            self._refresh_fts_index(conn, source_pk, v)
            conn.commit()
        finally:
            conn.close()

        return self._build_entry(v, created_at, now)

    def _load_existing(self, conn: sqlite3.Connection, source_id: str) -> sqlite3.Row | None:
        return cast(
            sqlite3.Row | None,
            conn.execute(
                "SELECT id, created_at FROM source_memory WHERE source_id = ?",
                (source_id,),
            ).fetchone(),
        )

    def _insert_source(
        self,
        conn: sqlite3.Connection,
        v: dict[str, Any],
        source_pk: int | None,
        created_at: datetime,
        now: datetime,
    ) -> int:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO source_memory (
                id, source_id, canonical_url, host, source_type, access_method,
                requires_auth, rate_limit_notes, reliability_score, quality_notes,
                search_hints, example_keys, example_urls, last_seen_at,
                discovery_campaign_id, meta, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_pk,
                v["source_id"],
                v["canonical_url"],
                v["host"],
                v["source_type"],
                v["access_method"],
                int(v["requires_auth"]),
                v["rate_limit_notes"],
                v["reliability_score"],
                v["quality_notes"],
                json.dumps(v["search_hints"], default=str),
                json.dumps(v["example_keys"], default=str),
                json.dumps(v["example_urls"], default=str),
                now.isoformat(),
                v["discovery_campaign_id"],
                json.dumps(v["meta"], default=str),
                created_at.isoformat(),
                now.isoformat(),
            ),
        )
        return source_pk if source_pk is not None else (cursor.lastrowid or 0)

    def _refresh_tags(self, conn: sqlite3.Connection, v: dict[str, Any]) -> None:
        conn.execute(
            "DELETE FROM source_memory_tags WHERE source_id = ?",
            (v["source_id"],),
        )
        tag_rows = (
            [(v["source_id"], tag, "topic") for tag in v["topic_tags"]]
            + [(v["source_id"], tag, "information") for tag in v["information_types"]]
            + [(v["source_id"], v["source_type"], "type")]
        )
        conn.executemany(
            "INSERT OR IGNORE INTO source_memory_tags (source_id, tag, tag_kind) VALUES (?, ?, ?)",
            tag_rows,
        )

    def _refresh_fts_index(
        self, conn: sqlite3.Connection, source_pk: int, v: dict[str, Any]
    ) -> None:
        """Index a fresh source row; contentless FTS5 does not support updates."""
        conn.execute(
            """
            INSERT INTO source_memory_fts (
                rowid, source_id, canonical_url, host, source_type, access_method,
                rate_limit_notes, quality_notes, search_hints, information_types, topic_tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_pk,
                v["source_id"],
                v["canonical_url"],
                v["host"],
                v["source_type"],
                v["access_method"],
                v["rate_limit_notes"],
                v["quality_notes"],
                json.dumps(v["search_hints"], default=str),
                " ".join(v["information_types"]),
                " ".join(v["topic_tags"]),
            ),
        )

    def _build_entry(
        self, v: dict[str, Any], created_at: datetime, now: datetime
    ) -> SourceMemoryEntry:
        return SourceMemoryEntry(
            source_id=v["source_id"],
            canonical_url=v["canonical_url"],
            host=v["host"],
            source_type=v["source_type"],
            information_types=v["information_types"],
            topic_tags=v["topic_tags"],
            access_method=v["access_method"],
            requires_auth=v["requires_auth"],
            rate_limit_notes=v["rate_limit_notes"],
            reliability_score=v["reliability_score"],
            quality_notes=v["quality_notes"],
            search_hints=v["search_hints"],
            example_keys=v["example_keys"],
            example_urls=v["example_urls"],
            last_seen_at=now,
            discovery_campaign_id=v["discovery_campaign_id"],
            meta=v["meta"],
            created_at=created_at,
            updated_at=now,
        )

    def get(self, source_id: str) -> SourceMemoryEntry | None:
        """Load a single source by its canonical id."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM source_memory WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_entry(row)

    def search(
        self,
        query: str | None = None,
        host: str | None = None,
        source_type: str | None = None,
        topic_tags: list[str] | None = None,
        information_types: list[str] | None = None,
        min_reliability: float | None = None,
        limit: int = 50,
    ) -> list[SourceMemoryEntry]:
        """Search the source memory.

        When ``query`` is provided, it is matched against the FTS index of
        URLs, notes, hints, and source types. Additional filters narrow the
        result set.
        """
        safe_query = sanitize_fts_query(query) if query else None
        sql = "SELECT sm.* FROM source_memory sm WHERE 1=1"
        params: list[Any] = []

        if safe_query:
            sql += (
                " AND sm.id IN ("
                "SELECT rowid FROM source_memory_fts WHERE source_memory_fts MATCH ?)"
            )
            params.append(safe_query)
        if host:
            sql += " AND sm.host = ?"
            params.append(host)
        if source_type:
            sql += " AND sm.source_type = ?"
            params.append(source_type)
        if min_reliability is not None:
            sql += " AND sm.reliability_score >= ?"
            params.append(min_reliability)
        if topic_tags:
            tag_sql, tag_params = self._tag_filter_sql(topic_tags, "topic")
            sql += tag_sql
            params.extend(tag_params)
        if information_types:
            tag_sql, tag_params = self._tag_filter_sql(information_types, "information")
            sql += tag_sql
            params.extend(tag_params)

        sql += " ORDER BY sm.reliability_score DESC, sm.last_seen_at DESC LIMIT ?"
        params.append(limit)

        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()

        return [self._row_to_entry(row) for row in rows]

    def get_by_tag(self, tag: str, tag_kind: str = "topic", limit: int = 50) -> list[SourceMemoryEntry]:
        """Return sources carrying a specific tag."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT sm.* FROM source_memory sm
                JOIN source_memory_tags t ON sm.source_id = t.source_id
                WHERE t.tag = ? AND t.tag_kind = ?
                ORDER BY sm.reliability_score DESC, sm.last_seen_at DESC
                LIMIT ?
                """,
                (tag, tag_kind, limit),
            ).fetchall()
        finally:
            conn.close()
        return [self._row_to_entry(row) for row in rows]

    def list_tags(self, tag_kind: str | None = None) -> list[str]:
        """Return all known tags, optionally filtered by kind."""
        conn = self._connect()
        try:
            if tag_kind is not None:
                rows = conn.execute(
                    "SELECT DISTINCT tag FROM source_memory_tags WHERE tag_kind = ? ORDER BY tag",
                    (tag_kind,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT DISTINCT tag FROM source_memory_tags ORDER BY tag"
                ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def list_hosts(self) -> list[str]:
        """Return all known hosts."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT host FROM source_memory ORDER BY host"
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows if row[0]]

    def list_source_types(self) -> list[str]:
        """Return all known source types."""
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT DISTINCT source_type FROM source_memory ORDER BY source_type"
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def delete(self, source_id: str) -> bool:
        """Remove a source from memory. Returns True if it existed."""
        conn = self._connect()
        try:
            cursor = conn.execute(
                "DELETE FROM source_memory WHERE source_id = ?",
                (source_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def clear(self) -> int:
        """Remove all sources. Use with care. Returns number of rows deleted."""
        conn = self._connect()
        try:
            conn.execute("DROP TABLE IF EXISTS source_memory_fts")
            conn.executescript(self.MIGRATIONS[2])
            cursor = conn.execute("DELETE FROM source_memory")
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def _row_to_entry(self, row: sqlite3.Row) -> SourceMemoryEntry:
        """Reconstruct a SourceMemoryEntry from a database row."""
        return SourceMemoryEntry(
            source_id=row["source_id"],
            canonical_url=row["canonical_url"],
            host=row["host"],
            source_type=row["source_type"],
            information_types=self._tags(row["source_id"], "information"),
            topic_tags=self._tags(row["source_id"], "topic"),
            access_method=row["access_method"],
            requires_auth=bool(row["requires_auth"]),
            rate_limit_notes=row["rate_limit_notes"],
            reliability_score=float(row["reliability_score"]),
            quality_notes=row["quality_notes"],
            search_hints=json.loads(row["search_hints"]),
            example_keys=json.loads(row["example_keys"]),
            example_urls=json.loads(row["example_urls"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            discovery_campaign_id=row["discovery_campaign_id"],
            meta=json.loads(row["meta"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    @staticmethod
    def _tag_filter_sql(tags: list[str], kind: str) -> tuple[str, list[Any]]:
        """Return a SQL fragment + params that require every tag in ``tags``.

        Uses an EXISTS subquery so the LIMIT is applied after tag filtering.
        """
        placeholders = ",".join("?" for _ in tags)
        in_clause = f"({placeholders})"
        sql = (
            " AND EXISTS ("  # nosec B608
            "SELECT 1 FROM source_memory_tags t "
            "WHERE t.source_id = sm.source_id AND t.tag_kind = ? "
            "AND t.tag IN " + in_clause + " "
            "GROUP BY t.source_id HAVING COUNT(DISTINCT t.tag) = ?)"
        )
        params: list[Any] = [kind, *tags, len(tags)]
        return sql, params

    def _tags(self, source_id: str, kind: str) -> list[str]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT tag FROM source_memory_tags "
                "WHERE source_id = ? AND tag_kind = ? ORDER BY tag",
                (source_id, kind),
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def stats(self) -> dict[str, Any]:
        """Return high-level statistics for dashboards and quick review."""
        conn = self._connect()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM source_memory"
            ).fetchone()[0]
            by_type = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT source_type, COUNT(*) FROM source_memory GROUP BY source_type"
                ).fetchall()
            }
            avg_reliability = conn.execute(
                "SELECT AVG(reliability_score) FROM source_memory"
            ).fetchone()[0]
        finally:
            conn.close()
        return {
            "total_sources": total,
            "by_type": by_type,
            "avg_reliability": avg_reliability or 0.0,
        }
