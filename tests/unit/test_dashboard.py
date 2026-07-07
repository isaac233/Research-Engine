"""Tests for the campaign analytics dashboard."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_engine.dashboard import CampaignDashboard
from research_engine.state import CampaignStage, CampaignStatus, CampaignStore, ResearchRequest


@pytest.fixture
def store(tmp_path: Path) -> CampaignStore:
    return CampaignStore(tmp_path / "state.db")


@pytest.fixture
def dashboard(store: CampaignStore) -> CampaignDashboard:
    return CampaignDashboard(store)


def _make_campaign(store: CampaignStore, query: str = "test query") -> str:
    request = ResearchRequest(query=query, context="ctx", max_sources=10)
    campaign = store.create_campaign(request)
    return campaign.id


def test_empty_metrics(dashboard: CampaignDashboard) -> None:
    metrics = dashboard.metrics()
    assert metrics.total == 0
    assert metrics.completed == 0
    assert metrics.failed == 0
    assert metrics.average_duration_seconds is None
    assert metrics.median_duration_seconds is None


def test_status_breakdown(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    c1 = _make_campaign(store, "q1")
    c2 = _make_campaign(store, "q2")
    c3 = _make_campaign(store, "q3")

    campaign = store.get_campaign(c1)
    assert campaign is not None
    store.update_campaign(campaign.with_status(CampaignStatus.COMPLETED))
    campaign = store.get_campaign(c2)
    assert campaign is not None
    store.update_campaign(campaign.with_status(CampaignStatus.FAILED))
    campaign = store.get_campaign(c3)
    assert campaign is not None
    store.update_campaign(campaign.with_status(CampaignStatus.PAUSED))

    metrics = dashboard.metrics()
    assert metrics.total == 3
    assert metrics.completed == 1
    assert metrics.failed == 1
    assert metrics.paused == 1
    assert metrics.status_counts == {
        "completed": 1,
        "failed": 1,
        "paused": 1,
    }


def test_stage_counts(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    c1 = _make_campaign(store, "q1")
    campaign = store.get_campaign(c1)
    assert campaign is not None
    store.update_campaign(campaign.with_stage(CampaignStage.DISCOVER))

    metrics = dashboard.metrics()
    assert metrics.stage_counts.get("discover") == 1


def test_duration_metrics(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    _make_campaign(store, "q1")
    metrics = dashboard.metrics()
    assert metrics.average_duration_seconds is not None
    assert metrics.median_duration_seconds is not None
    assert metrics.average_duration_seconds >= 0


def test_campaign_summary_unknown(dashboard: CampaignDashboard) -> None:
    assert dashboard.campaign_summary("does-not-exist") is None


def test_campaign_summary_stage_durations(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    campaign_id = _make_campaign(store, "q1")
    store.append_event(campaign_id, "stage_enter", {"stage": "discover"})
    store.append_event(campaign_id, "stage_exit", {"stage": "discover"})

    summary = dashboard.campaign_summary(campaign_id)
    assert summary is not None
    assert summary.campaign_id == campaign_id
    assert summary.query == "q1"
    assert summary.status == "pending"
    assert "discover" in summary.stage_durations
    assert summary.stage_durations["discover"] >= 0


def test_list_summaries(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    _make_campaign(store, "q1")
    _make_campaign(store, "q2")
    summaries = dashboard.list_summaries()
    assert len(summaries) == 2
    queries = {s.query for s in summaries}
    assert queries == {"q1", "q2"}


def test_generate_report_to_stdout(dashboard: CampaignDashboard) -> None:
    report = dashboard.generate_report()
    assert "# Research Engine Campaign Report" in report


def test_generate_report_to_file(store: CampaignStore, dashboard: CampaignDashboard, tmp_path: Path) -> None:
    _make_campaign(store, "q1")
    output = tmp_path / "report.md"
    dashboard.generate_report(output, project_root=tmp_path)
    assert output.exists()
    content = output.read_text(encoding="utf-8")
    assert "q1" in content
    assert "Total campaigns" in content


def test_stage_durations_ignore_missing_stage(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    campaign_id = _make_campaign(store, "q1")
    store.append_event(campaign_id, "stage_enter", {"other": "discover"})
    store.append_event(campaign_id, "stage_exit", {"other": "discover"})
    summary = dashboard.campaign_summary(campaign_id)
    assert summary is not None
    assert summary.stage_durations == {}


def test_stage_durations_accumulate_reentries(store: CampaignStore, dashboard: CampaignDashboard) -> None:
    campaign_id = _make_campaign(store, "q1")
    store.append_event(campaign_id, "stage_enter", {"stage": "discover"})
    store.append_event(campaign_id, "stage_enter", {"stage": "discover"})
    store.append_event(campaign_id, "stage_exit", {"stage": "discover"})

    summary = dashboard.campaign_summary(campaign_id)
    assert summary is not None
    assert summary.stage_durations["discover"] >= 0
