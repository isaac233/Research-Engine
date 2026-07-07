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


def test_discovery_stage_runs_pipeline() -> None:
    from research_engine.discovery.pipeline import DiscoveryPipeline
    from research_engine.discovery.schema import (
        DiscoveryResult,
        DuplicateGroup,
        Paper,
        ResolveResult,
    )

    class FakeDiscoveryPipeline(DiscoveryPipeline):
        def __init__(self) -> None:
            pass

        def run(self, query: str, context: str = "", max_sources: int = 50) -> DiscoveryResult:
            return DiscoveryResult(
                query=query,
                plan={"queries": [], "keywords": []},
                search_results=[],
                deduped_groups=[
                    DuplicateGroup(
                        canonical=Paper(title="Found Paper", source="fake", source_id="1", doi="10.1/1")
                    )
                ],
                snowball_papers=[],
                resolved=[
                    ResolveResult(
                        paper_key="10.1/1",
                        url="https://example.com/paper.pdf",
                        is_oa=True,
                        source="fake",
                        reason="test",
                    )
                ],
            )

    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(store, EventBus(store), discovery=FakeDiscoveryPipeline())
    campaign = orch.start_campaign(ResearchRequest(query="discovery test"))
    final = orch.run_campaign(campaign.id)

    assert final.status == CampaignStatus.COMPLETED
    events = store.get_events(campaign.id, "stage_exit")
    discover_event = next((e for e in events if e["payload"].get("stage") == "discover"), None)
    assert discover_event is not None
    assert discover_event["payload"]["result"]["canonical_count"] == 1
    assert discover_event["payload"]["result"]["resolved_count"] == 1
