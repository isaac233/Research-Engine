"""Unit tests for the campaign orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.discovery.schema import Paper
from research_engine.evaluation.deep_audit import DeepAuditor, DeepAuditResult
from research_engine.events import EventBus
from research_engine.extraction.structured import (
    ExtractedClaim,
    ExtractedSource,
    StructuredExtractor,
    extracted_source_to_dict,
)
from research_engine.orchestrator import Orchestrator
from research_engine.screening.ranker import SourceRanker
from research_engine.state import CampaignStatus, CampaignStore, ResearchRequest


def make_orchestrator() -> Orchestrator:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    return Orchestrator(store, EventBus(store))


def _source_dict(
    claims: list[ExtractedClaim] | None = None,
    paper: Paper | None = None,
) -> dict:
    paper = paper or Paper(title="Source", source="test", source_id="s1", doi="10.1/1")
    source = ExtractedSource(
        paper=paper,
        title=paper.title,
        summary="summary",
        methodology="",
        data_summary="",
        results_summary="",
        claims=claims or [],
        citations=[],
        conflicts=[],
        full_text_url="",
        is_oa=False,
        extraction_tool="test",
        error=None,
        meta={},
    )
    return extracted_source_to_dict(source)


def test_start_then_run_to_completion() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="run test"))
    assert campaign.status == CampaignStatus.PENDING

    final = orch.run_campaign(campaign.id)
    assert final.status == CampaignStatus.COMPLETED
    assert final.stage.value == "finalize"
    telemetry_events = orch.store.get_events(campaign.id, "telemetry_stage")
    assert len(telemetry_events) >= 1


def test_init_stage_records_metadata() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="init test"))
    result = orch._run_init(campaign)

    assert result["ok"] is True
    assert "init_at" in result
    updated = orch.store.get_campaign(campaign.id)
    assert updated is not None
    assert "init_at" in updated.meta
    assert updated.meta.get("cleanup_ok") is False


def test_plan_stage_stores_research_plan() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="plan test"))
    result = orch._run_plan(campaign)

    assert result["ok"] is True
    assert result["query_count"] >= 1
    updated = orch.store.get_campaign(campaign.id)
    assert updated is not None
    assert "plan" in updated.meta
    assert "queries" in updated.meta["plan"]


def test_finalize_stage_vacuums_and_records_receipt() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="finalize test"))
    orch.run_campaign(campaign.id)
    final = orch.store.get_campaign(campaign.id)
    assert final is not None

    assert final.meta.get("cleanup_ok") is True
    assert "finalized_at" in final.meta
    assert "cleanup_receipt" in final.meta


def test_status_snapshot() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="snapshot test"))
    snapshot = orch.status_snapshot(campaign.id)
    assert snapshot["stage"] == campaign.stage.value
    assert snapshot["status"] == campaign.status.value
    assert "progress_percent" in snapshot
    assert "remaining_stages" in snapshot
    assert "alerts" in snapshot


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


def test_screen_and_extract_stages_run() -> None:
    from research_engine.discovery.pipeline import DiscoveryPipeline
    from research_engine.discovery.schema import DiscoveryResult, DuplicateGroup, ResolveResult

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
                        canonical=Paper(
                            title="Found Paper",
                            source="fake",
                            source_id="1",
                            doi="10.1/1",
                            year=2024,
                            pdf_url="https://example.com/paper.pdf",
                        )
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
    orch = Orchestrator(
        store,
        EventBus(store),
        discovery=FakeDiscoveryPipeline(),
        ranker=SourceRanker(),
        extractor=StructuredExtractor(),
    )
    campaign = orch.start_campaign(ResearchRequest(query="screen extract test"))
    final = orch.run_campaign(campaign.id)

    assert final.status == CampaignStatus.COMPLETED
    events = store.get_events(campaign.id, "stage_exit")
    screen_event = next((e for e in events if e["payload"].get("stage") == "screen"), None)
    extract_event = next((e for e in events if e["payload"].get("stage") == "extract"), None)
    assert screen_event is not None
    assert extract_event is not None
    assert screen_event["payload"]["result"]["included_count"] == 1
    assert extract_event["payload"]["result"]["extracted_count"] == 1


def test_adversarial_and_evaluate_stages_run() -> None:
    from research_engine.discovery.pipeline import DiscoveryPipeline
    from research_engine.discovery.schema import DiscoveryResult, DuplicateGroup, ResolveResult

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
                        canonical=Paper(
                            title="Found Paper",
                            source="fake",
                            source_id="1",
                            doi="10.1/1",
                            year=2024,
                            pdf_url="https://example.com/paper.pdf",
                            abstract="We found that the new method improves accuracy by twelve percent.",
                        )
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
    orch = Orchestrator(
        store,
        EventBus(store),
        discovery=FakeDiscoveryPipeline(),
        ranker=SourceRanker(),
        extractor=StructuredExtractor(),
    )
    campaign = orch.start_campaign(ResearchRequest(query="adversarial eval test"))
    final = orch.run_campaign(campaign.id)

    assert final.status == CampaignStatus.COMPLETED
    events = store.get_events(campaign.id, "stage_exit")
    adversarial_event = next((e for e in events if e["payload"].get("stage") == "adversarial"), None)
    evaluate_event = next((e for e in events if e["payload"].get("stage") == "evaluate"), None)
    deliver_event = next((e for e in events if e["payload"].get("stage") == "deliver"), None)
    assert adversarial_event is not None
    assert evaluate_event is not None
    assert deliver_event is not None
    assert evaluate_event["payload"]["result"]["coverage_score"] > 0
    assert evaluate_event["payload"]["result"]["quality_score"] > 0


def test_adversarial_stage_records_challenge_triage() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="triage test"))
    campaign = campaign.with_meta("extracted_sources", [_source_dict()])
    campaign = orch.store.update_campaign(campaign)
    result = orch._run_adversarial(campaign)

    assert "triage" in result
    assert result["triage"] == {"high": 0, "medium": 0, "low": 0}
    updated = orch.store.get_campaign(campaign.id)
    assert updated is not None
    assert updated.meta.get("challenge_triage") == {"high": 0, "medium": 0, "low": 0}


def test_evaluate_stage_stores_improvement_proposals() -> None:
    orch = make_orchestrator()
    campaign = orch.start_campaign(ResearchRequest(query="proposals test"))
    campaign = campaign.with_meta("extracted_sources", [_source_dict()])
    campaign = orch.store.update_campaign(campaign)
    result = orch._run_evaluate(campaign)

    assert result["ok"] is True
    assert result["proposal_count"] >= 1
    updated = orch.store.get_campaign(campaign.id)
    assert updated is not None
    assert "improvement_proposals" in updated.meta


class FakeDeepAuditor(DeepAuditor):
    def __init__(self) -> None:
        super().__init__(provider=None)

    def audit(self, campaign_meta: dict, trigger: str = "periodic") -> DeepAuditResult:
        return DeepAuditResult(
            anomalies=["fake anomaly"],
            recommendations=["fake recommendation"],
            raw_response="raw",
        )


def test_evaluate_stage_runs_deep_audit_when_configured() -> None:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(store, EventBus(store), deep_auditor=FakeDeepAuditor())
    campaign = orch.start_campaign(ResearchRequest(query="audit test"))
    campaign = campaign.with_meta("extracted_sources", [_source_dict()])
    campaign = orch.store.update_campaign(campaign)
    result = orch._run_evaluate(campaign)

    assert result["ok"] is True
    assert "deep_audit" in result
    assert result["deep_audit"]["anomalies"] == ["fake anomaly"]
    updated = orch.store.get_campaign(campaign.id)
    assert updated is not None
    assert updated.meta.get("deep_audit", {}).get("recommendations") == ["fake recommendation"]
