"""Unit tests for the campaign orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import (
    DiscoveryResult,
    DuplicateGroup,
    Paper,
    ResolveResult,
    SearchResult,
)
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
from research_engine.state import CampaignStage, CampaignStatus, CampaignStore, ResearchRequest
from research_engine.storage.agent_history import (
    AgentActionOutcome,
    AgentHistory,
    AgentHistoryRecord,
)
from research_engine.storage.source_memory import SourceMemory


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


def test_screen_zero_inclusion_is_flagged_not_silent() -> None:
    """A non-empty candidate set that includes nothing must be made visible."""
    from types import SimpleNamespace

    class AllExcludingRanker:
        criteria = SimpleNamespace(name="strict")

        def rank(self, papers: list[Paper], query: str = "") -> list[SimpleNamespace]:
            return [
                SimpleNamespace(
                    paper=p,
                    criterion_scores=[],
                    total_score=0.0,
                    included=False,
                    reason="excluded",
                )
                for p in papers
            ]

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
                        canonical=Paper(title="Weak", source="fake", source_id="1", doi="10.1/1")
                    )
                ],
                snowball_papers=[],
                resolved=[],
            )

    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(
        store,
        EventBus(store),
        discovery=FakeDiscoveryPipeline(),
        ranker=AllExcludingRanker(),
        extractor=StructuredExtractor(),
    )
    campaign = orch.start_campaign(ResearchRequest(query="zero inclusion test"))
    final = orch.run_campaign(campaign.id)

    assert final.status == CampaignStatus.COMPLETED
    assert final.meta.get("screening_yielded_zero") is True
    events = store.get_events(campaign.id, "stage_exit")
    screen_event = next((e for e in events if e["payload"].get("stage") == "screen"), None)
    assert screen_event is not None
    assert "skipped" in screen_event["payload"]["result"]
    # Downstream stages must report an honest skip, not "not yet implemented".
    extract_event = next((e for e in events if e["payload"].get("stage") == "extract"), None)
    assert extract_event is not None
    assert "not yet implemented" not in extract_event["payload"]["result"].get("note", "")


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


def test_record_agent_action_no_op_without_history() -> None:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(store, EventBus(store))
    record = AgentHistoryRecord(
        campaign_id="c-no-history",
        agent_name="orchestrator",
        action_type="noop_test",
        outcome=AgentActionOutcome.SUCCESS,
    )
    returned = orch.record_agent_action(record)
    assert returned is record
    # No crash and no persistent history.
    assert orch.agent_history is None


def test_stage_enter_exit_recorded_in_agent_history() -> None:
    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    history = AgentHistory(tmp / "history.db")
    orch = Orchestrator(store, EventBus(store), agent_history=history)
    campaign = orch.start_campaign(ResearchRequest(query="history test"))
    orch.run_campaign(campaign.id)

    records = history.search(campaign_id=campaign.id, action_type="stage_enter")
    assert len(records) >= 1
    assert all(r.outcome == AgentActionOutcome.SUCCESS for r in records)

    exits = history.search(campaign_id=campaign.id, action_type="stage_exit")
    assert len(exits) >= 1
    assert all(r.agent_name == "orchestrator" for r in exits)


def test_discovery_stage_records_audit_and_source_memory() -> None:
    class FakeDiscoveryPipelineForMemory(DiscoveryPipeline):
        def __init__(self) -> None:
            pass

        def run(self, query: str, context: str = "", max_sources: int = 50) -> DiscoveryResult:
            return DiscoveryResult(
                query=query,
                plan={"queries": [], "keywords": ["machine", "learning"]},
                search_results=[
                    SearchResult(
                        source="semantic_scholar",
                        query="machine learning",
                        papers=[Paper(title="Paper A", source="semantic_scholar", source_id="1", doi="10.1/1")],
                    ),
                    SearchResult(
                        source="crossref",
                        query="machine learning",
                        papers=[Paper(title="Paper B", source="crossref", source_id="2", doi="10.1/2")],
                    ),
                ],
                deduped_groups=[
                    DuplicateGroup(
                        canonical=Paper(title="Paper A", source="semantic_scholar", source_id="1", doi="10.1/1")
                    )
                ],
                snowball_papers=[],
                resolved=[
                    ResolveResult(
                        paper_key="10.1/1",
                        url="https://example.com/paper.pdf",
                        is_oa=True,
                        source="semantic_scholar",
                        reason="test",
                    )
                ],
            )

    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    history = AgentHistory(tmp / "history.db")
    memory = SourceMemory(tmp / "memory.db")
    orch = Orchestrator(
        store,
        EventBus(store),
        discovery=FakeDiscoveryPipelineForMemory(),
        agent_history=history,
        source_memory=memory,
    )
    campaign = orch.start_campaign(ResearchRequest(query="machine learning"))
    final = orch.run_campaign(campaign.id)

    assert final.status == CampaignStatus.COMPLETED

    audit_records = history.search(campaign_id=campaign.id, action_type="discovery_search")
    assert len(audit_records) == 2
    sources = {r.source_name for r in audit_records}
    assert sources == {"semantic_scholar", "crossref"}

    semantic = memory.search(host="api.semanticscholar.org")
    assert len(semantic) == 1
    assert semantic[0].source_type == "academic_api"
    assert "paper_metadata" in semantic[0].information_types
    assert semantic[0].topic_tags == ["learning", "machine"]

    crossref = memory.search(host="api.crossref.org")
    assert len(crossref) == 1
    assert crossref[0].canonical_url == "https://api.crossref.org"


def test_source_memory_failure_event_redacts_url(monkeypatch) -> None:
    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    memory = SourceMemory(tmp / "memory.db")
    orch = Orchestrator(store, EventBus(store), source_memory=memory)

    def _explode(**kwargs) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(memory, "remember", _explode)
    orch.remember_source(
        canonical_url="https://user:pass@api.example.com/papers?api_key=secret",
        source_type="api",
        campaign_id="c1",
    )
    events = store.get_events("c1", "source_memory_failed")
    assert len(events) == 1
    redacted_url = events[0]["payload"]["canonical_url"]
    assert "user:pass@" not in redacted_url
    assert "api_key=[REDACTED]" in redacted_url


def test_stage_exit_records_error_when_result_not_ok(monkeypatch) -> None:
    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    history = AgentHistory(tmp / "history.db")
    orch = Orchestrator(store, EventBus(store), agent_history=history)
    campaign = orch.start_campaign(ResearchRequest(query="stage fail"))
    monkeypatch.setattr(orch, "_run_init", lambda _campaign: {"ok": False, "note": "bad"})

    orch.run_campaign(campaign.id)
    exits = history.search(campaign_id=campaign.id, action_type="stage_exit")
    init_exit = next((r for r in exits if r.meta.get("stage") == "init"), None)
    assert init_exit is not None
    assert init_exit.outcome == AgentActionOutcome.ERROR


def test_run_discover_rejects_overlong_query() -> None:
    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    orch = Orchestrator(store, EventBus(store))
    campaign = orch.start_campaign(ResearchRequest(query="x" * 1001))
    with pytest.raises(ValueError, match="1000"):
        orch.run_campaign(campaign.id)
    final = store.get_campaign(campaign.id)
    assert final is not None
    assert final.status == CampaignStatus.FAILED


def test_run_extract_skips_rejected_content_url() -> None:
    class FakeExtractor:
        def extract(self, paper, content=None, content_url=None, is_oa=False, fetch_fn=None):
            return _source_dict(paper=paper)

    tmp = Path(tempfile.mkdtemp())
    store = CampaignStore(tmp / "state.db")
    orch = Orchestrator(
        store,
        EventBus(store),
        extractor=FakeExtractor(),
    )
    campaign = orch.start_campaign(ResearchRequest(query="extract validation"))
    orch.store.update_campaign(
        campaign
        .with_stage(CampaignStage.EXTRACT)
        .with_meta(
            "included_papers",
            [Paper(title="P1", source="fake", source_id="1", doi="10.1/1").to_dict()],
        )
        .with_meta(
            "resolved_map",
            {
                "10.1/1": {"url": "file:///etc/passwd", "is_oa": True},
            },
        )
    )
    result = orch._run_extract(orch._require_campaign(campaign.id))
    assert result["extracted_count"] == 0
    rejected = store.get_events(campaign.id, "extraction_url_rejected")
    assert len(rejected) == 1
