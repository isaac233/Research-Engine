"""Tests for stage progress tracking."""

from __future__ import annotations

from research_engine.monitoring.progress import StageProgressTracker
from research_engine.state import Campaign, CampaignStage, CampaignStatus, ResearchRequest


def test_progress_at_init() -> None:
    tracker = StageProgressTracker()
    campaign = Campaign(
        id="c1",
        slug="test",
        request=ResearchRequest(query="test"),
        stage=CampaignStage.INIT,
        status=CampaignStatus.PENDING,
        created_at=None,  # type: ignore[arg-type]
        updated_at=None,  # type: ignore[arg-type]
    )
    percent, remaining = tracker.progress_and_remaining(campaign)
    assert percent > 0
    assert "plan" in remaining
    assert "finalize" in remaining


def test_progress_at_finalize_has_no_remaining() -> None:
    tracker = StageProgressTracker()
    campaign = Campaign(
        id="c1",
        slug="test",
        request=ResearchRequest(query="test"),
        stage=CampaignStage.FINALIZE,
        status=CampaignStatus.RUNNING,
        created_at=None,  # type: ignore[arg-type]
        updated_at=None,  # type: ignore[arg-type]
    )
    percent, remaining = tracker.progress_and_remaining(campaign)
    assert percent == 100
    assert remaining == []
