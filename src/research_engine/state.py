"""Campaign state dataclasses and SQLite-backed append-only store."""

from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum, auto
from pathlib import Path
from typing import Any


class CampaignStage(StrEnum):
    """Ordered lifecycle stages for a research campaign."""

    INIT = auto()
    PLAN = auto()
    DISCOVER = auto()
    SCREEN = auto()
    EXTRACT = auto()
    ADVERSARIAL = auto()
    EVALUATE = auto()
    DELIVER = auto()
    FINALIZE = auto()


class CampaignStatus(StrEnum):
    """Runtime status of a campaign."""

    PENDING = auto()
    RUNNING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    KILLED = auto()
    FAILED = auto()


@dataclass(frozen=True, slots=True)
class ResearchRequest:
    """Immutable research request from the main AI."""

    query: str
    context: str = ""
    max_sources: int = 50
    output_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.query or not self.query.strip():
            raise ValueError("Research query must be non-empty")
        if self.max_sources < 1:
            raise ValueError("max_sources must be >= 1")


@dataclass(frozen=True, slots=True)
class Campaign:
    """Immutable snapshot of a research campaign."""

    id: str
    slug: str
    request: ResearchRequest
    stage: CampaignStage
    status: CampaignStatus
    created_at: datetime
    updated_at: datetime
    meta: dict[str, Any] = field(default_factory=dict)

    def with_stage(self, stage: CampaignStage) -> Campaign:
        """Return a new Campaign with the given stage and updated timestamp."""
        return self._copy(stage=stage, status=self.status)

    def with_status(self, status: CampaignStatus) -> Campaign:
        """Return a new Campaign with the given status and updated timestamp."""
        return self._copy(stage=self.stage, status=status)

    def with_meta(self, key: str, value: Any) -> Campaign:
        """Return a new Campaign with an updated meta key."""
        new_meta = dict(self.meta)
        new_meta[key] = value
        return self._copy(stage=self.stage, status=self.status, meta=new_meta)

    def _copy(
        self,
        *,
        stage: CampaignStage,
        status: CampaignStatus,
        meta: dict[str, Any] | None = None,
    ) -> Campaign:
        now = datetime.now(UTC)
        return Campaign(
            id=self.id,
            slug=self.slug,
            request=self.request,
            stage=stage,
            status=status,
            created_at=self.created_at,
            updated_at=now,
            meta=meta if meta is not None else self.meta,
        )


def _slugify(query: str) -> str:
    """Create a short URL-safe slug from a query."""
    cleaned = "_".join(
        word.lower()
        for word in query.replace("-", " ").replace("_", " ").split()
        if word.isalnum()
    )
    return cleaned[:50] or "campaign"


class CampaignStore:
    """Append-only SQLite store for campaign state and events."""

    MIGRATIONS: tuple[str, ...] = (
        """
        CREATE TABLE IF NOT EXISTS campaigns (
            campaign_id TEXT PRIMARY KEY,
            slug TEXT NOT NULL,
            query TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '',
            max_sources INTEGER NOT NULL,
            output_path TEXT,
            stage TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            meta TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status);
        CREATE INDEX IF NOT EXISTS idx_campaigns_slug ON campaigns(slug);
        """,
        """
        CREATE TABLE IF NOT EXISTS events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            campaign_id TEXT NOT NULL,
            type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            timestamp TEXT NOT NULL,
            FOREIGN KEY (campaign_id) REFERENCES campaigns(campaign_id)
        );
        CREATE INDEX IF NOT EXISTS idx_events_campaign ON events(campaign_id);
        CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);
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
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.commit()
        finally:
            conn.close()

    def create_campaign(self, request: ResearchRequest) -> Campaign:
        """Create a new campaign and return its immutable state."""
        campaign_id = str(uuid.uuid4())
        slug = _slugify(request.query)
        now = datetime.now(UTC)
        campaign = Campaign(
            id=campaign_id,
            slug=slug,
            request=request,
            stage=CampaignStage.INIT,
            status=CampaignStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT INTO campaigns
                (campaign_id, slug, query, context, max_sources, output_path,
                 stage, status, created_at, updated_at, meta)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    campaign.id,
                    campaign.slug,
                    campaign.request.query,
                    campaign.request.context,
                    campaign.request.max_sources,
                    campaign.request.output_path,
                    campaign.stage.value,
                    campaign.status.value,
                    campaign.created_at.isoformat(),
                    campaign.updated_at.isoformat(),
                    json.dumps(campaign.meta),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.append_event(campaign.id, "campaign_created", {"slug": slug})
        return campaign

    def get_campaign(self, campaign_id: str) -> Campaign | None:
        """Load a campaign by id, or None if not found."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return self._row_to_campaign(row)

    def list_campaigns(self, status: CampaignStatus | None = None) -> list[Campaign]:
        """List campaigns, optionally filtered by status."""
        query = "SELECT * FROM campaigns"
        params: tuple[Any, ...] = ()
        if status is not None:
            query += " WHERE status = ?"
            params = (status.value,)
        query += " ORDER BY created_at DESC"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_campaign(row) for row in rows]

    def update_campaign(self, campaign: Campaign) -> Campaign:
        """Persist an updated campaign snapshot and return it."""
        now = datetime.now(UTC)
        updated = campaign._copy(stage=campaign.stage, status=campaign.status)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                UPDATE campaigns
                SET stage = ?, status = ?, updated_at = ?, meta = ?
                WHERE campaign_id = ?
                """,
                (
                    updated.stage.value,
                    updated.status.value,
                    now.isoformat(),
                    json.dumps(updated.meta),
                    updated.id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return updated

    def append_event(
        self,
        campaign_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        """Append an event to the log and return the generated event id."""
        payload = payload or {}
        now = datetime.now(UTC)
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                INSERT INTO events (campaign_id, type, payload, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (campaign_id, event_type, json.dumps(payload), now.isoformat()),
            )
            event_id = cursor.lastrowid
            conn.commit()
        finally:
            conn.close()
        return event_id or 0

    def get_events(self, campaign_id: str, event_type: str | None = None) -> list[dict[str, Any]]:
        """Return events for a campaign, optionally filtered by type."""
        query = "SELECT * FROM events WHERE campaign_id = ?"
        params: list[Any] = [campaign_id]
        if event_type is not None:
            query += " AND type = ?"
            params.append(event_type)
        query += " ORDER BY event_id ASC"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [
            {
                "event_id": row["event_id"],
                "campaign_id": row["campaign_id"],
                "type": row["type"],
                "payload": json.loads(row["payload"]),
                "timestamp": row["timestamp"],
            }
            for row in rows
        ]

    def _row_to_campaign(self, row: sqlite3.Row) -> Campaign:
        request = ResearchRequest(
            query=row["query"],
            context=row["context"],
            max_sources=row["max_sources"],
            output_path=row["output_path"],
        )
        return Campaign(
            id=row["campaign_id"],
            slug=row["slug"],
            request=request,
            stage=CampaignStage(row["stage"]),
            status=CampaignStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            meta=json.loads(row["meta"]),
        )
