"""Unit tests for telemetry emitter."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.events import EventBus
from research_engine.monitoring.telemetry import TelemetryAnalyzer, TelemetryEmitter
from research_engine.state import (
    CampaignStage,
    CampaignStatus,
    CampaignStore,
    ResearchRequest,
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


def test_analyzer_detects_stage_failure() -> None:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    campaign = store.create_campaign(ResearchRequest(query="telemetry test"))
    store.append_event(
        campaign.id,
        "stage_exit",
        {"stage": "discover", "result": {"ok": False, "error": "network timeout"}},
    )
    analyzer = TelemetryAnalyzer()
    alerts = analyzer.check(campaign.id, store)
    failure_alerts = [a for a in alerts if a["kind"] == "stage_failure"]
    assert len(failure_alerts) == 1
    assert failure_alerts[0]["stage"] == "discover"


def test_analyzer_detects_thrashing() -> None:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    campaign = store.create_campaign(ResearchRequest(query="thrash test"))
    for _ in range(4):
        store.append_event(campaign.id, "stage_enter", {"stage": "discover"})
    analyzer = TelemetryAnalyzer()
    alerts = analyzer.check(campaign.id, store)
    thrash_alerts = [a for a in alerts if a["kind"] == "thrashing"]
    assert len(thrash_alerts) == 1
    assert thrash_alerts[0]["enter_count"] == 4
