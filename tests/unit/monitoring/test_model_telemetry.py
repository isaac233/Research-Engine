"""Unit tests for model/GPU telemetry events."""

from __future__ import annotations

from typing import Any

from research_engine.monitoring.telemetry import TelemetryEmitter, lifecycle_telemetry_hook


class FakeBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict[str, Any]]] = []

    def emit(self, campaign_id: str, event_type: str, payload: dict[str, Any]) -> int:
        self.events.append((campaign_id, event_type, payload))
        return len(self.events)


def test_model_event_sanitizes_unknown_keys() -> None:
    bus = FakeBus()
    emitter = TelemetryEmitter(bus)  # type: ignore[arg-type]
    emitter.model_event("c1", "switch", {"from_tag": "a", "to_tag": "b", "secret": "leak"})
    _, event_type, payload = bus.events[-1]
    assert event_type == "telemetry_model"
    assert payload["event"] == "switch"
    assert payload["from_tag"] == "a"
    assert payload["to_tag"] == "b"
    assert "secret" not in payload  # unknown key stripped


def test_gpu_snapshot_event() -> None:
    bus = FakeBus()
    emitter = TelemetryEmitter(bus)  # type: ignore[arg-type]
    emitter.gpu_snapshot("c1", {"vram_used_mb": 3300.0, "vram_total_mb": 16000.0})
    _, event_type, payload = bus.events[-1]
    assert event_type == "telemetry_gpu"
    assert payload["vram_used_mb"] == 3300.0


def test_lifecycle_hook_forwards_to_model_event() -> None:
    bus = FakeBus()
    emitter = TelemetryEmitter(bus)  # type: ignore[arg-type]
    hook = lifecycle_telemetry_hook(emitter, "c9")
    hook("model_load", {"tag": "gemma4:12b", "ok": True})
    campaign_id, event_type, payload = bus.events[-1]
    assert campaign_id == "c9"
    assert event_type == "telemetry_model"
    assert payload["event"] == "model_load"
    assert payload["tag"] == "gemma4:12b"
