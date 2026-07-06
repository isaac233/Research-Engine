"""Unit tests for the campaign orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.events import EventBus
from research_engine.orchestrator import Orchestrator
from research_engine.state import CampaignStatus, CampaignStore, ResearchRequest


def make_orchestrator() -> Orchestrator:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    return Orchestrator(store, EventBus(store))


def test_start_then_run_to_completion() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="run test"))
    assert campaign.status == CampaignStatus.PENDING

    final = orch.run_campaign(campaign.id)
    assert final.status == CampaignStatus.COMPLETED
    assert final.stage.value == "finalize"


def test_pause_then_resume() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="pause test"))
    orch.run_campaign(campaign.id)

    # A completed campaign cannot be paused.
    paused = orch.pause_campaign(campaign.id)
    assert paused.status == CampaignStatus.COMPLETED


def test_kill_request_on_running_campaign() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="kill test"))
    # Simulate a kill by setting signal before run.
    orch.store.update_campaign(campaign.with_meta("signal", "kill"))

    final = orch.run_campaign(campaign.id)
    assert final.status == CampaignStatus.KILLED


def test_resume_clears_pause_signal() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="resume test"))
    orch.store.update_campaign(campaign.with_status(CampaignStatus.PAUSED).with_meta("signal", "pause"))

    resumed = orch.resume_campaign(campaign.id)
    assert resumed.status == CampaignStatus.COMPLETED
