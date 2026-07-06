"""Telemetry: stage receipts without PII."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from research_engine.events import EventBus
from research_engine.state import CampaignStage, CampaignStatus


class TelemetryEmitter:
    """Emit structured telemetry events for the orchestrator."""

    ALLOWED_META_KEYS = {"stage", "status", "duration_ms", "provider", "model"}

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus

    def stage_transition(
        self,
        campaign_id: str,
        stage: CampaignStage,
        status: CampaignStatus,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """Emit a sanitized stage transition telemetry event."""
        payload = {
            "stage": stage.value,
            "status": status.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        payload.update(self._sanitize(meta or {}))
        return self.event_bus.emit(campaign_id, "telemetry_stage", payload)

    def campaign_lifecycle(
        self,
        campaign_id: str,
        status: CampaignStatus,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """Emit a sanitized campaign lifecycle telemetry event."""
        payload = {
            "status": status.value,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        payload.update(self._sanitize(meta or {}))
        return self.event_bus.emit(campaign_id, "telemetry_campaign", payload)

    def _sanitize(self, meta: dict[str, Any]) -> dict[str, Any]:
        """Strip unknown keys to keep telemetry free of PII/surprises."""
        return {
            k: v
            for k, v in meta.items()
            if k in self.ALLOWED_META_KEYS and isinstance(v, (str, int, float, bool))
        }
