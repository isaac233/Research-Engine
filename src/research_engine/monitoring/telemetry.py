"""Telemetry: stage receipts without PII."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from research_engine.events import EventBus
from research_engine.state import CampaignStage, CampaignStatus, CampaignStore


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


class TelemetryAnalyzer:
    """Detect anomalies in campaign event history and emit alert events."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        stuck_threshold_seconds: float = 300.0,
    ) -> None:
        self.event_bus = event_bus
        self.stuck_threshold_seconds = stuck_threshold_seconds

    def check(self, campaign_id: str, store: CampaignStore) -> list[dict[str, Any]]:
        """Return alerts for stuck stages, failures, and thrashing."""
        events = store.get_events(campaign_id)
        alerts: list[dict[str, Any]] = []
        alerts.extend(self._check_stuck(events))
        alerts.extend(self._check_failures(events))
        alerts.extend(self._check_thrashing(events))
        if self.event_bus is not None:
            for alert in alerts:
                self.event_bus.emit(campaign_id, "telemetry_alert", alert)
        return alerts

    def _check_stuck(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        enters = [e for e in events if e.get("type") == "stage_enter"]
        exits = [e for e in events if e.get("type") == "stage_exit"]
        if not enters:
            return []
        latest_stage = enters[-1].get("payload", {}).get("stage")
        latest_exit_stage = exits[-1].get("payload", {}).get("stage") if exits else None
        if latest_stage == latest_exit_stage:
            return []
        try:
            dt = datetime.fromisoformat(enters[-1]["timestamp"])
        except (ValueError, KeyError):
            return []
        elapsed = (datetime.now(UTC) - dt).total_seconds()
        if elapsed > self.stuck_threshold_seconds:
            return [
                {
                    "kind": "stuck",
                    "stage": latest_stage,
                    "elapsed_seconds": elapsed,
                    "threshold_seconds": self.stuck_threshold_seconds,
                }
            ]
        return []

    def _check_failures(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        for event in events:
            if event.get("type") != "stage_exit":
                continue
            result = event.get("payload", {}).get("result", {})
            if isinstance(result, dict) and result.get("ok") is False:
                alerts.append(
                    {
                        "kind": "stage_failure",
                        "stage": event.get("payload", {}).get("stage"),
                        "reason": result.get("error", "unknown"),
                    }
                )
        return alerts

    def _check_thrashing(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for event in events:
            if event.get("type") != "stage_enter":
                continue
            stage = event.get("payload", {}).get("stage")
            if stage:
                counts[stage] = counts.get(stage, 0) + 1
        return [
            {"kind": "thrashing", "stage": stage, "enter_count": count}
            for stage, count in counts.items()
            if count > 3
        ]
