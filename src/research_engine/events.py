"""Append-only event bus for campaign telemetry and receipts."""

from __future__ import annotations

from typing import Any

from research_engine.state import CampaignStore


class EventBus:
    """Publish campaign events to the append-only store."""

    def __init__(self, store: CampaignStore) -> None:
        self.store = store

    def emit(
        self,
        campaign_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> int:
        """Emit an event and return its id."""
        return self.store.append_event(campaign_id, event_type, payload)
