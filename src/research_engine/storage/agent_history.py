"""Append-only audit history of agent actions for accountability and replay.

Records every significant action taken by project agents: URLs visited, APIs
called, sources queried, data gathered, and outcomes. The history is designed to
be detailed enough to answer questions about when, where, and why an agent did
something.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Any

from research_engine.storage._redaction import (
    redact_headers,
    redact_meta,
    redact_secrets,
    redact_url,
    sanitize_fts_query,
)


class AgentActionOutcome(StrEnum):
    """Controlled vocabulary for action outcomes."""

    SUCCESS = auto()
    FAILURE = auto()
    BLOCKED = auto()
    ERROR = auto()
    TIMEOUT = auto()
    RETRY = auto()
    CACHED = auto()


@dataclass(frozen=True, slots=True)
class AgentHistoryRecord:
    """Immutable snapshot of one recorded agent action.

    Fields are intentionally verbose so an agnostic AI (or human auditor) can
    reconstruct what happened without needing project-specific context.
    """

    history_id: int | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    campaign_id: str | None = None
    agent_name: str = ""
    action_type: str = ""
    target_url: str | None = None
    api_endpoint: str | None = None
    source_name: str | None = None
    source_id: str | None = None
    http_method: str | None = None
    request_headers: dict[str, str] = field(default_factory=dict)
    request_summary: str = ""
    response_status: int | None = None
    response_size_bytes: int | None = None
    response_summary: str = ""
    data_gathered_summary: str = ""
    outcome: AgentActionOutcome = AgentActionOutcome.SUCCESS
    reason: str = ""
    evidence_links: list[str] = field(default_factory=list)
    related_paper_keys: list[str] = field(default_factory=list)
    pii_redacted: bool = True
    audit_level: str = "normal"
    session_id: str | None = None
    trace_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation for audit export and AI review."""
        return {
            "history_id": self.history_id,
            "timestamp": self.timestamp.isoformat(),
            "campaign_id": self.campaign_id,
            "agent_name": self.agent_name,
            "action_type": self.action_type,
            "target_url": self.target_url,
            "api_endpoint": self.api_endpoint,
            "source_name": self.source_name,
            "source_id": self.source_id,
            "http_method": self.http_method,
            "request_headers": dict(self.request_headers),
            "request_summary": self.request_summary,
            "response_status": self.response_status,
            "response_size_bytes": self.response_size_bytes,
            "response_summary": self.response_summary,
            "data_gathered_summary": self.data_gathered_summary,
            "outcome": self.outcome.value,
            "reason": self.reason,
            "evidence_links": list(self.evidence_links),
            "related_paper_keys": list(self.related_paper_keys),
            "pii_redacted": self.pii_redacted,
            "audit_level": self.audit_level,
            "session_id": self.session_id,
            "trace_id": self.trace_id,
            "meta": dict(self.meta),
        }


class AgentHistory:
    """Append-only SQLite store of agent actions with full-text search."""

    MIGRATIONS: tuple[str, ...] = (
        """
        CREATE TABLE IF NOT EXISTS agent_history (
            history_id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            campaign_id TEXT,
            agent_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target_url TEXT,
            api_endpoint TEXT,
            source_name TEXT,
            source_id TEXT,
            http_method TEXT,
            request_headers TEXT NOT NULL DEFAULT '{}',
            request_summary TEXT NOT NULL DEFAULT '',
            response_status INTEGER,
            response_size_bytes INTEGER,
            response_summary TEXT NOT NULL DEFAULT '',
            data_gathered_summary TEXT NOT NULL DEFAULT '',
            outcome TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            evidence_links TEXT NOT NULL DEFAULT '[]',
            related_paper_keys TEXT NOT NULL DEFAULT '[]',
            pii_redacted INTEGER NOT NULL DEFAULT 1,
            audit_level TEXT NOT NULL DEFAULT 'normal',
            session_id TEXT,
            trace_id TEXT,
            meta TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_agent_history_campaign ON agent_history(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_agent_history_agent ON agent_history(agent_name);
        CREATE INDEX IF NOT EXISTS idx_agent_history_action ON agent_history(action_type);
        CREATE INDEX IF NOT EXISTS idx_agent_history_url ON agent_history(target_url);
        CREATE INDEX IF NOT EXISTS idx_agent_history_endpoint ON agent_history(api_endpoint);
        CREATE INDEX IF NOT EXISTS idx_agent_history_source ON agent_history(source_name);
        CREATE INDEX IF NOT EXISTS idx_agent_history_outcome ON agent_history(outcome);
        CREATE INDEX IF NOT EXISTS idx_agent_history_timestamp ON agent_history(timestamp);
        CREATE INDEX IF NOT EXISTS idx_agent_history_session ON agent_history(session_id);
        CREATE INDEX IF NOT EXISTS idx_agent_history_trace ON agent_history(trace_id);
        CREATE INDEX IF NOT EXISTS idx_agent_history_audit ON agent_history(audit_level);
        """,
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS agent_history_fts USING fts5(
            agent_name,
            action_type,
            target_url,
            api_endpoint,
            source_name,
            request_summary,
            response_summary,
            data_gathered_summary,
            reason,
            evidence_links,
            related_paper_keys,
            content='',
            content_rowid='rowid'
        );
        """,
    )

    # Column order must match _insert_record's hard-coded SQL.
    _COLUMNS: tuple[str, ...] = (
        "timestamp",
        "campaign_id",
        "agent_name",
        "action_type",
        "target_url",
        "api_endpoint",
        "source_name",
        "source_id",
        "http_method",
        "request_headers",
        "request_summary",
        "response_status",
        "response_size_bytes",
        "response_summary",
        "data_gathered_summary",
        "outcome",
        "reason",
        "evidence_links",
        "related_paper_keys",
        "pii_redacted",
        "audit_level",
        "session_id",
        "trace_id",
        "meta",
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

    def _redact_record(self, record: AgentHistoryRecord) -> tuple[dict[str, Any], datetime]:
        """Return a redacted values dict and the record timestamp."""
        now = record.timestamp
        redacted_api_endpoint = (
            redact_url(record.api_endpoint)
            if record.api_endpoint and record.api_endpoint.startswith(("http://", "https://"))
            else redact_secrets(record.api_endpoint or "")
        )
        return {
            "timestamp": now.isoformat(),
            "campaign_id": record.campaign_id,
            "agent_name": record.agent_name,
            "action_type": record.action_type,
            "target_url": redact_url(record.target_url),
            "api_endpoint": redacted_api_endpoint,
            "source_name": record.source_name,
            "source_id": record.source_id,
            "http_method": record.http_method,
            "request_headers": json.dumps(redact_headers(record.request_headers), default=str),
            "request_summary": redact_secrets(record.request_summary),
            "response_status": record.response_status,
            "response_size_bytes": record.response_size_bytes,
            "response_summary": redact_secrets(record.response_summary),
            "data_gathered_summary": redact_secrets(record.data_gathered_summary),
            "outcome": str(record.outcome),
            "reason": redact_secrets(record.reason),
            "evidence_links": json.dumps(
                [redact_url(link) for link in record.evidence_links], default=str
            ),
            "related_paper_keys": json.dumps(record.related_paper_keys, default=str),
            "pii_redacted": int(record.pii_redacted),
            "audit_level": record.audit_level,
            "session_id": record.session_id,
            "trace_id": record.trace_id,
            "meta": json.dumps(redact_meta(record.meta), default=str),
        }, now

    def _insert_record(
        self, conn: sqlite3.Connection, values: dict[str, Any]
    ) -> int:
        cursor = conn.execute(
            f"""
            INSERT INTO agent_history (
                {', '.join(self._COLUMNS)}
            ) VALUES ({', '.join('?' for _ in self._COLUMNS)})
            """,  # nosec B608 - columns are a hard-coded class constant
            tuple(values[c] for c in self._COLUMNS),
        )
        return cursor.lastrowid or 0

    def _insert_fts_row(
        self,
        conn: sqlite3.Connection,
        history_id: int,
        values: dict[str, Any],
    ) -> None:
        conn.execute(
            """
            INSERT INTO agent_history_fts (
                rowid, agent_name, action_type, target_url, api_endpoint,
                source_name, request_summary, response_summary, data_gathered_summary,
                reason, evidence_links, related_paper_keys
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                history_id,
                values["agent_name"],
                values["action_type"],
                values["target_url"] or "",
                values["api_endpoint"] or "",
                values["source_name"] or "",
                values["request_summary"],
                values["response_summary"],
                values["data_gathered_summary"],
                values["reason"],
                values["evidence_links"],
                values["related_paper_keys"],
            ),
        )

    def _build_redacted_record(
        self, record: AgentHistoryRecord, history_id: int, values: dict[str, Any], now: datetime
    ) -> AgentHistoryRecord:
        data = {name: getattr(record, name) for name in record.__dataclass_fields__}
        data["history_id"] = history_id
        data["timestamp"] = now
        data["request_headers"] = json.loads(values["request_headers"])
        data["target_url"] = values["target_url"]
        data["api_endpoint"] = values["api_endpoint"]
        data["request_summary"] = values["request_summary"]
        data["response_summary"] = values["response_summary"]
        data["data_gathered_summary"] = values["data_gathered_summary"]
        data["reason"] = values["reason"]
        data["evidence_links"] = json.loads(values["evidence_links"])
        data["meta"] = json.loads(values["meta"])
        return AgentHistoryRecord(**data)

    def record(self, record: AgentHistoryRecord) -> AgentHistoryRecord:
        """Persist an agent action and return it with the assigned history_id."""
        values, now = self._redact_record(record)
        conn = self._connect()
        try:
            history_id = self._insert_record(conn, values)
            self._insert_fts_row(conn, history_id, values)
            conn.commit()
        finally:
            conn.close()
        return self._build_redacted_record(record, history_id, values, now)

    def get(self, history_id: int) -> AgentHistoryRecord | None:
        """Load a single history record by id."""
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM agent_history WHERE history_id = ?",
                (history_id,),
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_record(row)

    def search(
        self,
        query: str | None = None,
        campaign_id: str | None = None,
        agent_name: str | None = None,
        action_type: str | None = None,
        outcome: AgentActionOutcome | str | None = None,
        source_name: str | None = None,
        target_url: str | None = None,
        audit_level: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
        limit: int = 100,
    ) -> list[AgentHistoryRecord]:
        """Search agent history by text and structured filters."""
        safe_query = sanitize_fts_query(query) if query else None
        sql, params = self._search_sql(
            safe_query=safe_query,
            campaign_id=campaign_id,
            agent_name=agent_name,
            action_type=action_type,
            outcome=outcome,
            source_name=source_name,
            target_url=target_url,
            audit_level=audit_level,
            start=start,
            end=end,
            limit=limit,
        )
        conn = self._connect()
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(sql, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_record(row) for row in rows]

    def _search_sql(
        self,
        safe_query: str | None,
        campaign_id: str | None,
        agent_name: str | None,
        action_type: str | None,
        outcome: AgentActionOutcome | str | None,
        source_name: str | None,
        target_url: str | None,
        audit_level: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> tuple[str, list[Any]]:
        if safe_query:
            sql = (
                "SELECT h.* FROM agent_history h "
                "JOIN agent_history_fts fts ON h.rowid = fts.rowid "
                "WHERE agent_history_fts MATCH ?"
            )
            params: list[Any] = [safe_query]
        else:
            sql = "SELECT * FROM agent_history WHERE 1=1"
            params = []

        def add_filter(column: str, value: Any) -> None:
            nonlocal sql
            sql += f" AND {column} = ?"  # nosec B608 - column names are hard-coded below
            params.append(value)

        if campaign_id is not None:
            add_filter("campaign_id", campaign_id)
        if agent_name is not None:
            add_filter("agent_name", agent_name)
        if action_type is not None:
            add_filter("action_type", action_type)
        if outcome is not None:
            add_filter("outcome", outcome.value if isinstance(outcome, AgentActionOutcome) else outcome)
        if source_name is not None:
            add_filter("source_name", source_name)
        if target_url is not None:
            add_filter("target_url", target_url)
        if audit_level is not None:
            add_filter("audit_level", audit_level)
        if start is not None:
            sql += " AND timestamp >= ?"
            params.append(start.isoformat())
        if end is not None:
            sql += " AND timestamp <= ?"
            params.append(end.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        return sql, params

    def recent(
        self,
        agent_name: str | None = None,
        action_type: str | None = None,
        limit: int = 50,
    ) -> list[AgentHistoryRecord]:
        """Return the most recent records with optional agent/action filters."""
        return self.search(
            agent_name=agent_name,
            action_type=action_type,
            limit=limit,
        )

    def summarize_campaign(self, campaign_id: str) -> dict[str, Any]:
        """Return a high-level summary of all actions for a campaign."""
        conn = self._connect()
        try:
            total = conn.execute(
                "SELECT COUNT(*) FROM agent_history WHERE campaign_id = ?",
                (campaign_id,),
            ).fetchone()[0]
            outcomes = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT outcome, COUNT(*) FROM agent_history WHERE campaign_id = ? GROUP BY outcome",
                    (campaign_id,),
                ).fetchall()
            }
            action_types = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT action_type, COUNT(*) FROM agent_history WHERE campaign_id = ? GROUP BY action_type",
                    (campaign_id,),
                ).fetchall()
            }
            sources = [
                row[0]
                for row in conn.execute(
                    "SELECT DISTINCT source_name FROM agent_history WHERE campaign_id = ? AND source_name IS NOT NULL",
                    (campaign_id,),
                ).fetchall()
            ]
            first = conn.execute(
                "SELECT timestamp FROM agent_history WHERE campaign_id = ? ORDER BY timestamp ASC LIMIT 1",
                (campaign_id,),
            ).fetchone()
            last = conn.execute(
                "SELECT timestamp FROM agent_history WHERE campaign_id = ? ORDER BY timestamp DESC LIMIT 1",
                (campaign_id,),
            ).fetchone()
        finally:
            conn.close()

        return {
            "campaign_id": campaign_id,
            "total_actions": total,
            "outcomes": outcomes,
            "action_types": action_types,
            "sources_touched": sources,
            "first_action_at": first[0] if first else None,
            "last_action_at": last[0] if last else None,
        }

    def export_range(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
        campaign_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Export records in JSON-friendly form for external audit."""
        records = self.search(
            campaign_id=campaign_id,
            start=start,
            end=end,
            limit=10000,
        )
        return [r.to_dict() for r in records]

    def stats(self) -> dict[str, Any]:
        """Return high-level statistics for dashboards."""
        conn = self._connect()
        try:
            total = conn.execute("SELECT COUNT(*) FROM agent_history").fetchone()[0]
            by_outcome = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT outcome, COUNT(*) FROM agent_history GROUP BY outcome"
                ).fetchall()
            }
            by_agent = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT agent_name, COUNT(*) FROM agent_history GROUP BY agent_name"
                ).fetchall()
            }
            sensitive = conn.execute(
                "SELECT COUNT(*) FROM agent_history WHERE audit_level = 'sensitive'"
            ).fetchone()[0]
        finally:
            conn.close()
        return {
            "total_actions": total,
            "by_outcome": by_outcome,
            "by_agent": by_agent,
            "sensitive_actions": sensitive,
        }

    def _row_to_record(self, row: sqlite3.Row) -> AgentHistoryRecord:
        return AgentHistoryRecord(
            history_id=row["history_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            campaign_id=row["campaign_id"],
            agent_name=row["agent_name"],
            action_type=row["action_type"],
            target_url=row["target_url"],
            api_endpoint=row["api_endpoint"],
            source_name=row["source_name"],
            source_id=row["source_id"],
            http_method=row["http_method"],
            request_headers=json.loads(row["request_headers"]),
            request_summary=row["request_summary"],
            response_status=row["response_status"],
            response_size_bytes=row["response_size_bytes"],
            response_summary=row["response_summary"],
            data_gathered_summary=row["data_gathered_summary"],
            outcome=AgentActionOutcome(row["outcome"]),
            reason=row["reason"],
            evidence_links=json.loads(row["evidence_links"]),
            related_paper_keys=json.loads(row["related_paper_keys"]),
            pii_redacted=bool(row["pii_redacted"]),
            audit_level=row["audit_level"],
            session_id=row["session_id"],
            trace_id=row["trace_id"],
            meta=json.loads(row["meta"]),
        )
