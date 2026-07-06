"""Unit tests for campaign state dataclasses and store."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from research_engine.state import (
    CampaignStage,
    CampaignStatus,
    CampaignStore,
    ResearchRequest,
)


def test_research_request_rejects_empty_query() -> None:
    with pytest.raises(ValueError, match="query must be non-empty"):
        ResearchRequest(query="")
    with pytest.raises(ValueError, match="query must be non-empty"):
        ResearchRequest(query="   ")


def test_research_request_rejects_invalid_max_sources() -> None:
    with pytest.raises(ValueError, match="max_sources must be"):
        ResearchRequest(query="test", max_sources=0)


def test_campaign_store_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CampaignStore(Path(tmp) / "state.db")
        request = ResearchRequest(query="test query", context="ctx", max_sources=10)
        campaign = store.create_campaign(request)

        loaded = store.get_campaign(campaign.id)
        assert loaded is not None
        assert loaded.id == campaign.id
        assert loaded.slug == "test_query"
        assert loaded.request.query == "test query"
        assert loaded.stage == CampaignStage.INIT
        assert loaded.status == CampaignStatus.PENDING


def test_campaign_store_events() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CampaignStore(Path(tmp) / "state.db")
        campaign = store.create_campaign(ResearchRequest(query="events test"))
        event_id = store.append_event(campaign.id, "test_event", {"x": 1})
        assert event_id > 0

        events = store.get_events(campaign.id)
        assert len(events) >= 2  # created + test
        assert any(e["type"] == "test_event" for e in events)


def test_campaign_update_is_immutable() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CampaignStore(Path(tmp) / "state.db")
        campaign = store.create_campaign(ResearchRequest(query="immutable"))
        updated = store.update_campaign(campaign.with_stage(CampaignStage.PLAN))

        assert updated.id == campaign.id
        assert updated.stage == CampaignStage.PLAN
        assert campaign.stage == CampaignStage.INIT  # original unchanged

        reloaded = store.get_campaign(campaign.id)
        assert reloaded is not None
        assert reloaded.stage == CampaignStage.PLAN
