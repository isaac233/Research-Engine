"""Tests for time-to-completion estimation."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from research_engine.monitoring.estimator import TimeEstimator
from research_engine.monitoring.progress import StageProgressTracker
from research_engine.state import CampaignStage, CampaignStore, ResearchRequest


def _store_with_timed_stages(tmp_path: Path) -> tuple[CampaignStore, str]:
    store = CampaignStore(tmp_path / "state.db")
    campaign = store.create_campaign(ResearchRequest(query="eta test"))
    for stage in ["init", "plan", "discover", "screen"]:
        store.append_event(campaign.id, "stage_enter", {"stage": stage})
        time.sleep(0.05)
        store.append_event(campaign.id, "stage_exit", {"stage": stage})
        time.sleep(0.05)
    return store, campaign.id


def test_estimator_uses_history_for_remaining_stages() -> None:
    tmp = Path(tempfile.mkdtemp())
    store, campaign_id = _store_with_timed_stages(tmp)
    estimator = TimeEstimator(store)
    tracker = StageProgressTracker()
    campaign = store.get_campaign(campaign_id)
    assert campaign is not None
    # "screen" is in the remaining list and has history from the timed stages.
    campaign = campaign.with_stage(CampaignStage("discover"))
    eta, note = estimator.predict_remaining(campaign, tracker)
    assert eta is not None
    assert eta >= 0
    assert "history" in note


def test_estimator_fallback_when_no_history() -> None:
    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    campaign = store.create_campaign(ResearchRequest(query="eta fallback"))
    estimator = TimeEstimator(store)
    tracker = StageProgressTracker()
    campaign = store.get_campaign(campaign.id)
    assert campaign is not None
    eta, note = estimator.predict_remaining(campaign, tracker)
    assert eta is not None
    assert "heuristic" in note
