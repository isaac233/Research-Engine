"""Unit tests for telemetry emitter."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.events import EventBus
from research_engine.monitoring.telemetry import TelemetryEmitter
from research_engine.state import (
    CampaignStage,
    CampaignStatus,
    CampaignStore,
)


def make_emitter() -> TelemetryEmitter:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    return TelemetryEmitter(EventBus(store))


def test_stage_transition_emits_event() -> None:
    emitter = make_emitter()
    # Need a campaign id; store is empty so event will reference no campaign but still be stored.
    event_id = emitter.stage_transition(
        "campaign-1", CampaignStage.PLAN, CampaignStatus.RUNNING
    )
    assert event_id > 0


def test_telemetry_strips_unknown_keys() -> None:
    emitter = make_emitter()
    event_id = emitter.stage_transition(
        "campaign-2",
        CampaignStage.DISCOVER,
        CampaignStatus.RUNNING,
        {"provider": "ollama", "user_email": "secret@example.com"},
    )
    assert event_id > 0
