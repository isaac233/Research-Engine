"""Campaign orchestrator: state machine + lifecycle + pause/resume/kill."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from research_engine.adversarial.challenge import (
    ChallengeDispatcher,
    challenge_to_dict,
    verification_to_dict,
)
from research_engine.adversarial.devil import DevilAgent
from research_engine.adversarial.verifier import Verifier
from research_engine.browser.ai_browser import AIBrowser
from research_engine.cleanup.janitor import CleanupJanitor
from research_engine.config import EngineConfig
from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.query_decomposer import plan_objectives
from research_engine.discovery.query_planner import QueryPlanner
from research_engine.discovery.schema import Paper
from research_engine.evaluation.deep_audit import DeepAuditor
from research_engine.evaluation.harness import EvaluationHarness
from research_engine.evaluation.improvement import ImprovementProposer
from research_engine.evaluation.reporter import Reporter
from research_engine.events import EventBus
from research_engine.extraction.markdownify import markdownify
from research_engine.extraction.structured import (
    StructuredExtractor,
    extracted_source_from_dict,
    extracted_source_to_dict,
)
from research_engine.llm.lane_roster import LaneRoster
from research_engine.llm.lifecycle import ModelLifecycleManager
from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.monitoring.estimator import TimeEstimator
from research_engine.monitoring.gpu_probe import GpuProbe
from research_engine.monitoring.progress import StageProgressTracker
from research_engine.monitoring.telemetry import TelemetryAnalyzer, TelemetryEmitter
from research_engine.orchestrator_instrumentation import OrchestratorInstrumentation
from research_engine.planning.handoff import HandoffDoc
from research_engine.planning.outline_builder import OutlineBuilder
from research_engine.planning.react_planner import PlanResult, ReactPlanner, SourceRef
from research_engine.planning.summary_feedback import refine_query, summarize_page
from research_engine.screening.enricher import enrich_snippets
from research_engine.screening.ranker import SourceRanker
from research_engine.screening.url_filter import prefer_fetchable
from research_engine.state import (
    Campaign,
    CampaignStage,
    CampaignStatus,
    CampaignStore,
    ResearchRequest,
)
from research_engine.storage._redaction import redact_payload, redact_secrets, redact_url
from research_engine.storage.agent_history import (
    AgentActionOutcome,
    AgentHistory,
    AgentHistoryRecord,
)
from research_engine.storage.artifacts import ArtifactManager
from research_engine.storage.source_memory import SourceMemory
from research_engine.synthesis.attribute_writer import AttributeFirstWriter
from research_engine.synthesis.deepen import deepen_report
from research_engine.synthesis.section_writer import SectionWriter
from research_engine.synthesis.synthesizer import (
    Synthesizer,
    drop_failed_claims,
    unique_insight_filter,
)
from research_engine.util.parallel import (
    item_timeout_from_env,
    max_workers_from_env,
    parallel_map,
)

# Candidates the ReAct loop pulls per refined sub-query before ranking+reading.
_REACT_PER_QUERY = 10
# ReAct budget. Sequential Ollama summarisation caps practical volume (~1 page/2-3s
# + fetch), so the defaults keep one task to minutes while still banking well above
# the linear ~11. Raise via env for an overnight high-volume run toward WebWeaver's
# ~100. ponytail: fixed budget; a GPU-parallel summariser is the real speed upgrade.
_REACT_MAX_PAGES = 16
_REACT_PER_OBJECTIVE = 3
# Hard wall-clock cap per task so a live run can never hang (the smoke-test waste).
_REACT_MAX_SECONDS = 600


def _react_budget() -> tuple[int, int, float]:
    """(max_pages, per_objective_pages, max_seconds) from env, else the defaults."""
    def _int(name: str, default: int) -> int:
        try:
            return max(1, int(os.environ.get(name, "")))
        except ValueError:
            return default

    return (
        _int("RESEARCH_ENGINE_REACT_MAX_PAGES", _REACT_MAX_PAGES),
        _int("RESEARCH_ENGINE_REACT_PER_OBJECTIVE", _REACT_PER_OBJECTIVE),
        float(_int("RESEARCH_ENGINE_REACT_MAX_SECONDS", _REACT_MAX_SECONDS)),
    )


def _writer_length() -> tuple[int, int]:
    """(max_sentences_per_section, max_tokens_per_section) from env, else defaults.

    RACE is reference-normalized against a ~63k-char reference; the default ~13k brief
    is 1/5 scale. Raising these lets the section writer reach reference length when the
    evidence supports it. Defaults preserve current behavior (8 sentences, 1200 tokens).
    """
    def _int(name: str, default: int) -> int:
        try:
            return max(1, int(os.environ.get(name, "")))
        except ValueError:
            return default

    return (
        _int("RESEARCH_ENGINE_WRITER_MAX_SENTENCES", 8),
        _int("RESEARCH_ENGINE_WRITER_MAX_TOKENS", 1200),
    )


def _react_per_objective_searches() -> int:
    """How many refined searches an under-filled objective may retry (Lever 2).

    Balances retrieval across ALL asked dimensions instead of piling the budget on the
    dominant serp topic; default 1 = current single-search behavior.
    """
    try:
        return max(1, int(os.environ.get("RESEARCH_ENGINE_REACT_PER_OBJECTIVE_SEARCHES", "")))
    except ValueError:
        return 1


def _react_seeded_outline() -> bool:
    """Build the react outline as one section per objective (Lever 1) when set.

    The default evidence-driven outline drifts to the banked evidence's dominant topic;
    seeding from the objectives keeps the report on the question's own dimensions.
    Env-gated so the default path is unchanged.
    """
    return bool(os.environ.get("RESEARCH_ENGINE_REACT_SEEDED_OUTLINE"))


def _react_anchored_outline() -> bool:
    """Task-anchor the react outline (question's dimensions drive sections) when set.

    The default evidence-driven outline drifts to whatever topic the banked spans
    dominate (measured: live react on task 51 = a healthcare essay for a market-size
    question, RACE instruction_following ~8.65/100). Env-gated so the default path is
    unchanged; on = experiment on the live surface that actually shows the failure.
    """
    return bool(os.environ.get("RESEARCH_ENGINE_REACT_ANCHORED_OUTLINE"))


def _react_dbg(msg: str) -> None:
    """Diagnostic trace for the ReAct path, gated on RESEARCH_ENGINE_REACT_DEBUG.

    Compares the in-campaign react run to the standalone _react_plan probe to find
    why the loop banks ~0 spans inside a full campaign but ~174 alone (HANDOFF bug).
    """
    if os.environ.get("RESEARCH_ENGINE_REACT_DEBUG"):
        print(f"[react-dbg] {msg}", file=sys.stderr, flush=True)


def _progress(msg: str) -> None:
    """Emit a pipeline progress line (gated on RESEARCH_ENGINE_PROGRESS).

    Long collection stages (screen/extract) do many sequential LLM calls without a
    per-item disk write, so a run looks frozen to a file-watching stall monitor even
    when healthy. These stderr lines give the watchdog a live progress signal and the
    operator visibility into where a run actually is.
    """
    if os.environ.get("RESEARCH_ENGINE_PROGRESS"):
        print(f"[progress] {msg}", file=sys.stderr, flush=True)


def _resolve_byte_fetcher(browser: Any) -> Callable[[str], bytes]:
    """Return a callable that actually fetches page bytes for ``browser``.

    The default browser is an ``UnblockProbe`` whose own ``fetch_bytes`` only
    serves unblock actions and raises on a normal URL — but it wraps a working
    ``RawHTTPBrowser`` at ``.http``. Prefer that inner client; a browser that
    fetches directly (RawHTTPBrowser, CDP driver) is used as-is. Without this,
    page enrichment, full-text extraction, page-bound evidence, and
    verify-before-cite all silently fail to fetch.
    """
    inner = getattr(browser, "http", None)
    fetcher = inner.fetch_bytes if inner is not None else browser.fetch_bytes
    return cast("Callable[[str], bytes]", fetcher)


class Orchestrator(OrchestratorInstrumentation):
    """Drive a research campaign through its lifecycle stages."""

    STAGE_ORDER: tuple[CampaignStage, ...] = (
        CampaignStage.INIT,
        CampaignStage.PLAN,
        CampaignStage.DISCOVER,
        CampaignStage.SCREEN,
        CampaignStage.EXTRACT,
        CampaignStage.ADVERSARIAL,
        CampaignStage.EVALUATE,
        CampaignStage.DELIVER,
        CampaignStage.FINALIZE,
    )

    def __init__(
        self,
        store: CampaignStore,
        event_bus: EventBus | None = None,
        browser: AIBrowser | None = None,
        discovery: DiscoveryPipeline | None = None,
        ranker: SourceRanker | None = None,
        extractor: StructuredExtractor | None = None,
        devil: DevilAgent | None = None,
        verifier: Verifier | None = None,
        eval_harness: EvaluationHarness | None = None,
        reporter: Reporter | None = None,
        project_root: Path | str | None = None,
        progress_tracker: StageProgressTracker | None = None,
        estimator: TimeEstimator | None = None,
        telemetry_emitter: TelemetryEmitter | None = None,
        telemetry_analyzer: TelemetryAnalyzer | None = None,
        deep_auditor: DeepAuditor | None = None,
        source_memory: SourceMemory | None = None,
        agent_history: AgentHistory | None = None,
        gpu_probe: GpuProbe | None = None,
        synthesizer: Synthesizer | None = None,
        lifecycle: ModelLifecycleManager | None = None,
        lane_roster: LaneRoster | None = None,
    ) -> None:
        self.store = store
        self.event_bus = event_bus or EventBus(store)
        self.browser = browser
        self.discovery = discovery
        self.ranker = ranker
        self.extractor = extractor
        self.devil = devil or DevilAgent()
        self.verifier = verifier or Verifier()
        self.eval_harness = eval_harness or EvaluationHarness()
        self.reporter = reporter or Reporter()
        resolved_root = Path(project_root) if project_root else Path(store.db_path).parent
        self.config = EngineConfig(resolved_root)
        self.artifacts = ArtifactManager(self.config)
        self.progress_tracker = progress_tracker or StageProgressTracker()
        self.estimator = estimator
        self.telemetry_emitter = telemetry_emitter or TelemetryEmitter(self.event_bus)
        self.telemetry_analyzer = telemetry_analyzer or TelemetryAnalyzer(self.event_bus)
        self.deep_auditor = deep_auditor
        self.source_memory = source_memory
        self.agent_history = agent_history
        self.gpu_probe = gpu_probe
        self.synthesizer = synthesizer
        self.lifecycle = lifecycle
        self.lane_roster = lane_roster
        # Deliverable writer: "synth" (default) or "attribute_first" (Phase 1.0).
        self.writer_mode = "synth"
        # Retrieval planner: "linear" (default single-pass) or "react" (iterative
        # gap-driven ReAct loop that co-evolves the outline with search, #8).
        self.planner_mode = "linear"

    BLOCKER_KEYWORDS = {
        "cannot find",
        "can't find",
        "no free",
        "no public",
        "missing data",
        "need a source",
        "need an api",
        "unknown api",
        "failing dependency",
        "how to",
        "find a library",
        "find a source",
    }

    def start_campaign(self, request: ResearchRequest) -> Campaign:
        """Create and persist a new campaign."""
        campaign = self.store.create_campaign(request)
        if self._is_blocker(request.query):
            campaign = self.store.update_campaign(campaign.with_meta("campaign_type", "unblocking"))
        self.event_bus.emit(
            campaign.id,
            "stage_enter",
            {"stage": campaign.stage.value, "status": campaign.status.value},
        )
        return campaign

    def _is_blocker(self, query: str) -> bool:
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.BLOCKER_KEYWORDS)

    def run_campaign(self, campaign_id: str) -> Campaign:
        """Run or resume a campaign from its current stage to completion."""
        campaign = self._require_campaign(campaign_id)

        if campaign.status == CampaignStatus.COMPLETED:
            return campaign
        if campaign.status == CampaignStatus.KILLED:
            return campaign

        campaign = self._set_status(campaign, CampaignStatus.RUNNING)
        current_index = self._stage_index(campaign.stage)

        for stage in self.STAGE_ORDER[current_index:]:
            campaign = self._enter_stage(campaign, stage)
            signal = campaign.meta.get("signal")
            if signal == "pause":
                campaign = self._set_status(campaign, CampaignStatus.PAUSED)
                campaign = self.store.update_campaign(campaign.with_meta("signal", None))
                self.event_bus.emit(campaign.id, "campaign_paused", {"stage": stage.value})
                return campaign
            if signal == "kill":
                campaign = self._set_status(campaign, CampaignStatus.KILLED)
                campaign = self.store.update_campaign(campaign.with_meta("signal", None))
                self.event_bus.emit(campaign.id, "campaign_killed", {"stage": stage.value})
                return campaign
            campaign = self._execute_stage(campaign, stage)

        campaign = self._set_status(campaign, CampaignStatus.COMPLETED)
        self.event_bus.emit(campaign.id, "campaign_completed", {})
        return campaign

    def pause_campaign(self, campaign_id: str) -> Campaign:
        """Signal a running campaign to pause at the next safe boundary."""
        campaign = self._require_campaign(campaign_id)
        if campaign.status != CampaignStatus.RUNNING:
            return campaign
        campaign = self.store.update_campaign(campaign.with_meta("signal", "pause"))
        self.event_bus.emit(campaign_id, "pause_requested", {"stage": campaign.stage.value})
        return campaign

    def resume_campaign(self, campaign_id: str) -> Campaign:
        """Resume a paused campaign."""
        campaign = self._require_campaign(campaign_id)
        if campaign.status != CampaignStatus.PAUSED:
            return campaign
        campaign = self._set_status(campaign, CampaignStatus.RUNNING)
        campaign = self.store.update_campaign(campaign.with_meta("signal", None))
        self.event_bus.emit(campaign_id, "campaign_resumed", {"stage": campaign.stage.value})
        return self.run_campaign(campaign_id)

    def kill_campaign(self, campaign_id: str) -> Campaign:
        """Signal a campaign to stop."""
        campaign = self._require_campaign(campaign_id)
        if campaign.status in {CampaignStatus.COMPLETED, CampaignStatus.KILLED}:
            return campaign
        campaign = self.store.update_campaign(campaign.with_meta("signal", "kill"))
        self.event_bus.emit(campaign_id, "kill_requested", {"stage": campaign.stage.value})
        if campaign.status == CampaignStatus.PAUSED:
            campaign = self._set_status(campaign, CampaignStatus.KILLED)
            return self.store.update_campaign(campaign.with_meta("signal", None))
        return campaign

    def _require_campaign(self, campaign_id: str) -> Campaign:
        campaign = self.store.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign not found: {campaign_id}")
        return campaign

    def _stage_index(self, stage: CampaignStage) -> int:
        try:
            return self.STAGE_ORDER.index(stage)
        except ValueError as exc:
            raise ValueError(f"Unknown stage: {stage}") from exc

    def _enter_stage(self, campaign: Campaign, stage: CampaignStage) -> Campaign:
        if campaign.stage != stage:
            campaign = campaign.with_stage(stage)
            campaign = self.store.update_campaign(campaign)
        self.event_bus.emit(
            campaign.id,
            "stage_enter",
            {"stage": stage.value, "status": campaign.status.value},
        )
        self.telemetry_emitter.stage_transition(
            campaign.id,
            stage,
            campaign.status,
            {"stage": stage.value, "status": campaign.status.value},
        )
        self.record_agent_action(
            AgentHistoryRecord(
                campaign_id=campaign.id,
                agent_name="orchestrator",
                action_type="stage_enter",
                request_summary=f"Entering stage {stage.value} for campaign {campaign.id}",
                outcome=AgentActionOutcome.SUCCESS,
                audit_level="normal",
                meta={"stage": stage.value, "status": campaign.status.value},
            )
        )
        return campaign

    def _execute_stage(self, campaign: Campaign, stage: CampaignStage) -> Campaign:
        handler_name = f"_run_{stage.value}"
        handler = getattr(self, handler_name, self._run_stub)
        _progress(f"stage START {stage.value}")
        stage_start = datetime.now(UTC)
        try:
            result = handler(campaign)
        except Exception as exc:
            campaign = self._set_status(campaign, CampaignStatus.FAILED)
            self.event_bus.emit(
                campaign.id,
                "stage_failed",
                {"stage": stage.value, "error": redact_secrets(str(exc))},
            )
            raise
        _progress(
            f"stage END   {stage.value} "
            f"[{(datetime.now(UTC) - stage_start).total_seconds():.0f}s]"
        )
        self.event_bus.emit(
            campaign.id,
            "stage_exit",
            {"stage": stage.value, "result": redact_payload(result)},
        )
        self.telemetry_emitter.stage_transition(
            campaign.id,
            stage,
            campaign.status,
            {"stage": stage.value, "status": campaign.status.value},
        )
        self.telemetry_analyzer.check(campaign.id, self.store)
        self.record_agent_action(
            AgentHistoryRecord(
                campaign_id=campaign.id,
                agent_name="orchestrator",
                action_type="stage_exit",
                request_summary=f"Completed stage {stage.value} for campaign {campaign.id}",
                response_summary=f"ok={result.get('ok')} note={result.get('note')}",
                outcome=(
                    AgentActionOutcome.ERROR
                    if not result.get("ok") or result.get("error")
                    else AgentActionOutcome.SUCCESS
                ),
                audit_level="normal",
                meta={"stage": stage.value, "status": campaign.status.value},
            )
        )
        return self._require_campaign(campaign.id)

    def _set_status(self, campaign: Campaign, status: CampaignStatus) -> Campaign:
        updated = campaign.with_status(status)
        updated = self.store.update_campaign(updated)
        self.telemetry_emitter.campaign_lifecycle(
            updated.id,
            status,
            {"status": status.value},
        )
        return updated

    def status_snapshot(self, campaign_id: str) -> dict[str, Any]:
        """Return a concise status snapshot for a campaign."""
        campaign = self._require_campaign(campaign_id)
        progress_percent, remaining_stages = self.progress_tracker.progress_and_remaining(
            campaign
        )
        eta_seconds: int | None = None
        if self.estimator is not None:
            eta_seconds, _ = self.estimator.predict_remaining(
                campaign, self.progress_tracker
            )
        alerts = self.telemetry_analyzer.check(campaign_id, self.store)
        snapshot: dict[str, Any] = {
            "campaign_id": campaign.id,
            "stage": campaign.stage.value,
            "status": campaign.status.value,
            "progress_percent": progress_percent,
            "eta_seconds": eta_seconds,
            "remaining_stages": remaining_stages,
            "alerts": alerts,
            "models": self._stage_models(campaign),
        }
        if self.gpu_probe is not None:
            gpu = self.gpu_probe.snapshot()
            snapshot["gpu"] = gpu.as_dict() if gpu is not None else None
        return snapshot

    @staticmethod
    def _stage_models(campaign: Campaign) -> dict[str, str]:
        """Which model handled model-driven stages (from persisted extraction meta)."""
        models: dict[str, str] = {}
        extracted = campaign.meta.get("extracted_sources", [])
        tools = {
            s.get("extraction_tool", "")
            for s in extracted
            if isinstance(s, dict) and str(s.get("extraction_tool", "")).startswith("llm:")
        }
        if tools:
            models["extract"] = ", ".join(sorted(tools))
        return models

    # --- Stage handlers ---

    def _run_stub(self, campaign: Campaign) -> dict[str, Any]:
        """Safety default for a stage with no handler. All stages are implemented;
        this only fires if a new stage is added without a `_run_<stage>` method."""
        return {"note": f"no handler for stage {campaign.stage.value}"}

    def _run_skipped(self, campaign: Campaign, reason: str) -> dict[str, Any]:
        """Report an implemented stage that had no input to act on.

        Distinct from ``_run_stub`` so telemetry and agent history record an
        honest "skipped: <reason>" instead of a misleading "not yet
        implemented", making a silently-empty pipeline visible.
        """
        return {"ok": True, "skipped": reason, "note": f"{campaign.stage.value} skipped: {reason}"}

    def _run_init(self, campaign: Campaign) -> dict[str, Any]:
        """Initialize campaign metadata and record start time."""
        now = datetime.now(UTC).isoformat()
        self.store.update_campaign(
            campaign.with_meta("init_at", now).with_meta("cleanup_ok", False)
        )
        return {"ok": True, "init_at": now}

    def _run_plan(self, campaign: Campaign) -> dict[str, Any]:
        """Build a research plan and store it in campaign metadata."""
        planner = QueryPlanner()
        plan = planner.plan(
            campaign.request.query,
            context=campaign.request.context,
            max_sources=campaign.request.max_sources,
        )
        plan_dict: dict[str, Any] = {
            "queries": [
                {"source": q.source, "query": q.query, "rationale": q.rationale, "priority": q.priority}
                for q in plan.queries
            ],
            "keywords": plan.keywords,
            "rationale": plan.rationale,
        }
        self.store.update_campaign(campaign.with_meta("plan", plan_dict))
        return {"ok": True, "query_count": len(plan_dict["queries"])}

    def _run_discover(self, campaign: Campaign) -> dict[str, Any]:
        """Dispatch discovery or unblocking probe depending on campaign type."""
        self._validate_request_input(campaign)
        if campaign.meta.get("campaign_type") == "unblocking" and self.browser is not None:
            result = self.browser.unblock(campaign.request.query)
            self.record_agent_action(
                AgentHistoryRecord(
                    campaign_id=campaign.id,
                    agent_name="browser",
                    action_type="unblock_probe",
                    request_summary=campaign.request.query,
                    response_summary=str(result.content or "")[:500],
                    outcome=AgentActionOutcome.SUCCESS if result.ok else AgentActionOutcome.FAILURE,
                    reason=result.error or "",
                    audit_level="normal",
                    meta={"action": result.action.value},
                )
            )
            return {
                "ok": result.ok,
                "action": result.action.value,
                "content_preview": str(result.content or "")[:500],
                "error": result.error,
                "meta": result.meta,
            }
        if self.discovery is not None:
            discovery_result = self.discovery.run(
                campaign.request.query,
                context=campaign.request.context,
                max_sources=campaign.request.max_sources,
            )
            canonical_papers = [g.canonical.to_dict() for g in discovery_result.deduped_groups]
            resolved_map = {r.paper_key: r for r in discovery_result.resolved}
            self.store.update_campaign(
                campaign.with_meta("canonical_papers", canonical_papers)
                .with_meta(
                    "resolved_map",
                    {
                        k: {
                            "url": redact_url(r.url) if r.url else None,
                            "is_oa": r.is_oa,
                            "source": r.source,
                        }
                        for k, r in resolved_map.items()
                    },
                )
            )
            for sr in discovery_result.search_results:
                status_code = getattr(sr, "status_code", None)
                self.record_agent_action(
                    AgentHistoryRecord(
                        campaign_id=campaign.id,
                        agent_name=sr.source,
                        action_type="discovery_search",
                        api_endpoint=sr.query,
                        response_status=status_code,
                        response_summary=str(sr.error or f"{len(sr.papers)} papers")[:500],
                        outcome=AgentActionOutcome.ERROR if sr.error else AgentActionOutcome.SUCCESS,
                        reason=sr.error or "",
                        source_name=sr.source,
                        audit_level="normal",
                    )
                )
                canonical_url = self.SOURCE_CANONICAL_URLS.get(sr.source)
                if canonical_url is not None:
                    self.remember_source(
                        canonical_url=canonical_url,
                        source_type="academic_api",
                        information_types=["paper_metadata", "abstracts", "citations"],
                        topic_tags=self._plan_keywords(campaign),
                        access_method="api",
                        reliability_score=0.7,
                        quality_notes=sr.error or "",
                        campaign_id=campaign.id,
                        meta={
                            "status_code": status_code,
                            "paper_count": len(sr.papers),
                            "adapter": sr.source,
                        },
                    )
            return {
                "ok": True,
                "canonical_count": len(discovery_result.deduped_groups),
                "resolved_count": len(discovery_result.resolved),
                "snowball_count": len(discovery_result.snowball_papers),
                "sources": [r.source for r in discovery_result.search_results],
                "errors": [r.error for r in discovery_result.search_results if r.error],
            }
        return self._run_stub(campaign)

    def _run_screen(self, campaign: Campaign) -> dict[str, Any]:
        """Screen canonical papers from discovery using the configured ranker."""
        canonical_data = campaign.meta.get("canonical_papers", [])
        if not canonical_data or self.ranker is None:
            return self._run_skipped(campaign, "no canonical papers or ranker unavailable")
        papers = [Paper.from_dict(d) for d in canonical_data]
        # Web snippets (~150 chars) starve the relevance rubric and extraction;
        # fetch the page for thin web sources so screening sees real content.
        if self.browser is not None:
            papers = enrich_snippets(papers, fetch_fn=_resolve_byte_fetcher(self.browser))
        scorecards = self.ranker.rank(papers, query=campaign.request.query)
        # Fetchability filter: within the relevance-passed set, float likely-fetchable
        # HTML above PDFs/DOIs/paywalls BEFORE the source-count cut, so the extraction
        # budget banks evidence instead of 403s (the binding constraint on volume).
        passed = prefer_fetchable(
            [s for s in scorecards if s.included],
            url_of=lambda s: s.paper.url or s.paper.pdf_url,
        )
        included = passed[: campaign.request.max_sources]
        # Zero inclusions from a non-empty candidate set means downstream stages
        # will silently no-op, so flag it rather than complete with an empty brief.
        yielded_zero = bool(scorecards) and not included
        # Honesty flag: a discovery pool that is mostly off-topic means the
        # query hit the wrong sources — surface it, don't ship a thin brief.
        relevance_failures = sum(
            1
            for s in scorecards
            for c in s.criterion_scores
            if c.criterion_name == "relevance" and c.value is not None and not c.passed
        )
        yielded_offtopic = bool(scorecards) and relevance_failures * 2 >= len(scorecards)
        campaign = campaign.with_meta(
            "scorecards", [self._scorecard_to_dict(s) for s in scorecards]
        ).with_meta("included_papers", [s.paper.to_dict() for s in included])
        if yielded_zero:
            campaign = campaign.with_meta("screening_yielded_zero", True)
        if yielded_offtopic:
            campaign = campaign.with_meta("screening_yielded_offtopic", True)
        self.store.update_campaign(campaign)
        result: dict[str, Any] = {
            "ok": True,
            "screened_count": len(scorecards),
            "included_count": len(included),
            "criteria_set": self.ranker.criteria.name,
        }
        if yielded_zero:
            result["skipped"] = (
                f"0 of {len(scorecards)} sources passed criteria "
                f"'{self.ranker.criteria.name}'"
            )
        if yielded_offtopic:
            result["offtopic"] = (
                f"{relevance_failures} of {len(scorecards)} candidates failed the "
                "relevance rubric; discovery likely queried the wrong sources"
            )
        return result

    def _switch_lane(self, campaign: Campaign, stage_name: str) -> None:
        """Load the model assigned to this stage, evicting the previous one.

        No-op unless a lifecycle manager + roster are configured. Keeps at most
        one model resident (VRAM does not stack across stages) and records the
        switch in telemetry.
        """
        if self.lifecycle is None or self.lane_roster is None:
            return
        plan = campaign.meta.get("resolved_plan", {})
        lane_name = (plan.get("lane_assignment", {}) or {}).get(stage_name)
        if not lane_name:
            return
        try:
            tag = self.lane_roster.lane(lane_name).tag
            num_ctx = self.lane_roster.lane(lane_name).num_ctx
        except KeyError:
            return
        if tag and tag != self.lifecycle.current:
            self.lifecycle.switch(tag, num_ctx=num_ctx)
            self.telemetry_emitter.model_event(
                campaign.id, "switch", {"stage": stage_name, "to_tag": tag}
            )

    def _run_extract(self, campaign: Campaign) -> dict[str, Any]:
        """Extract structured fields from included papers."""
        # The ReAct planner does its OWN gap-driven retrieval at evaluate-time, so the
        # linear per-page extract here is only an unused fallback that DOUBLE-PAYS the
        # slowest stage (~20-30 min/task of fetch+LLM extract). Skip it when react owns
        # retrieval (env-gated) to make react runs practical. The react brief supplies
        # the deliverable; if react banks nothing the brief is honestly flagged empty.
        if self.planner_mode == "react" and os.environ.get("RESEARCH_ENGINE_REACT_SKIP_COLLECT"):
            return self._run_skipped(campaign, "react planner owns retrieval (collect skipped)")
        self._switch_lane(campaign, "extract")
        included_data = campaign.meta.get("included_papers", [])
        if not included_data or self.extractor is None:
            return self._run_skipped(campaign, "no included papers to extract")
        resolved_map = campaign.meta.get("resolved_map", {})
        fetch_fn = _resolve_byte_fetcher(self.browser) if self.browser is not None else None
        # URL validation + event emission (SQLite writes) stay on this thread; only
        # the pure fetch+LLM extract calls are parallelised (no shared store state),
        # so higher evidence volume doesn't serialise into a ~30-min/task wall.
        work: list[tuple[Paper, str | None, bool]] = []
        for paper_dict in included_data:
            paper = Paper.from_dict(paper_dict)
            resolved = resolved_map.get(paper.key, {})
            content_url = resolved.get("url")
            try:
                self._validate_url(content_url)
            except ValueError as exc:
                self.event_bus.emit(
                    campaign.id,
                    "extraction_url_rejected",
                    {
                        "paper_key": paper.key,
                        "url": redact_url(content_url),
                        "reason": str(exc),
                    },
                )
                continue
            work.append((paper, content_url, bool(resolved.get("is_oa", False))))

        def _extract_one(item: tuple[Paper, str | None, bool]) -> dict[str, Any]:
            paper, content_url, is_oa = item
            source = self.extractor.extract(  # type: ignore[union-attr]
                paper, content=None, content_url=content_url, is_oa=is_oa, fetch_fn=fetch_fn
            )
            return extracted_source_to_dict(source)

        settled = 0

        def _on_settle(index: int, ok: bool) -> None:
            # Fires for every item incl. timeouts/failures — so a slow batch is visible
            # and never looks frozen to the stall monitor. url is best-effort.
            nonlocal settled
            settled += 1
            url = (work[index][0].url or work[index][0].title or "")[:60]
            _progress(f"extract {settled}/{len(work)} {'ok ' if ok else 'FAIL'} {url}")

        _progress(f"extract START {len(work)} sources")
        results = parallel_map(
            _extract_one,
            work,
            max_workers=max_workers_from_env(),
            item_timeout=item_timeout_from_env(),
            on_settle=_on_settle,
        )
        extracted: list[dict[str, Any]] = [r for r in results if r is not None]
        self.store.update_campaign(campaign.with_meta("extracted_sources", extracted))

        # Make the model that did the work visible (telemetry + audit log).
        tools = sorted({s.get("extraction_tool", "") for s in extracted})
        model_tool = next((t for t in tools if t.startswith("llm:")), tools[0] if tools else "")
        self.telemetry_emitter.model_event(
            campaign.id, "assignment", {"stage": "extract", "tag": model_tool}
        )
        self.record_agent_action(
            AgentHistoryRecord(
                campaign_id=campaign.id,
                agent_name="extractor",
                action_type="extract",
                request_summary=f"Extracted {len(extracted)} sources",
                response_summary=f"tool={model_tool}",
                outcome=AgentActionOutcome.SUCCESS,
                audit_level="normal",
                meta={"model": model_tool, "extracted_count": len(extracted)},
            )
        )
        return {
            "ok": True,
            "extracted_count": len(extracted),
            "model": model_tool,
        }

    def _scorecard_to_dict(self, scorecard: Any) -> dict[str, Any]:
        return {
            "paper": scorecard.paper.to_dict(),
            "criterion_scores": [
                {
                    "criterion_name": s.criterion_name,
                    "passed": s.passed,
                    "value": s.value,
                    "score": s.score,
                    "reason": s.reason,
                }
                for s in scorecard.criterion_scores
            ],
            "total_score": scorecard.total_score,
            "included": scorecard.included,
            "reason": scorecard.reason,
        }

    def _run_adversarial(self, campaign: Campaign) -> dict[str, Any]:
        """Run Devil and Verifier over extracted sources."""
        extracted_data = campaign.meta.get("extracted_sources", [])
        if not extracted_data:
            return self._run_skipped(campaign, "no extracted sources to challenge")
        sources = [extracted_source_from_dict(d) for d in extracted_data]
        challenges = self.devil.challenge(sources, query=campaign.request.query)
        verifications = self.verifier.verify(sources)
        dispatcher = ChallengeDispatcher()
        triage = dispatcher.dispatch(challenges)
        triage_counts = {bucket: len(items) for bucket, items in triage.items()}
        self.store.update_campaign(
            campaign.with_meta("challenges", [challenge_to_dict(c) for c in challenges])
            .with_meta("verifications", [verification_to_dict(v) for v in verifications])
            .with_meta("challenge_triage", triage_counts)
        )
        return {
            "ok": True,
            "challenge_count": len(challenges),
            "high_severity_count": sum(1 for c in challenges if c.severity == "high"),
            "verification_count": len(verifications),
            "failed_verification_count": sum(1 for v in verifications if not v.ok),
            "triage": triage_counts,
        }

    def _write_handoff(self, campaign: Campaign, sources: list[Any]) -> None:
        """Record the extract->evaluate model switch so intent carries forward."""
        extract_model = next(
            (
                s.get("extraction_tool", "")
                for s in campaign.meta.get("extracted_sources", [])
                if isinstance(s, dict)
            ),
            "",
        )
        synth_model = self.synthesizer.model if self.synthesizer else ""
        HandoffDoc(
            campaign_id=campaign.id,
            from_stage="extract",
            to_stage="evaluate",
            from_model=extract_model,
            to_model=synth_model or "synth",
            goal=campaign.request.query,
            produced=f"{len(sources)} sources extracted with methods/data/results",
            open_questions="",
            next_task="Synthesize replication-grade insights; keep unique per-source findings.",
        ).write(self.config.engine_data_dir)

    def _run_evaluate(self, campaign: Campaign) -> dict[str, Any]:
        """Evaluate extracted output and produce a report."""
        inputs = self._load_evaluation_inputs(campaign)
        if inputs is None:
            return self._run_skipped(campaign, "no extracted sources to evaluate")
        sources, challenges, verifications = inputs
        if self.synthesizer is not None:
            self._switch_lane(campaign, "evaluate")
            self._write_handoff(campaign, sources)
        report, brief, proposals = self._build_report_and_brief(
            sources, challenges, verifications, campaign.request.query
        )
        deep_audit_payload = self._build_deep_audit_payload(campaign)
        updated = self._build_evaluation_meta(campaign, report, brief, proposals)
        if deep_audit_payload is not None:
            updated = updated.with_meta("deep_audit", deep_audit_payload)
        self.store.update_campaign(updated)
        return self._build_evaluation_result(report, brief, proposals, deep_audit_payload)

    def _load_evaluation_inputs(
        self, campaign: Campaign
    ) -> tuple[list[Any], list[Any], list[Any]] | None:
        """Deserialize sources, challenges, and verifications from campaign meta."""
        extracted_data = campaign.meta.get("extracted_sources", [])
        if not extracted_data:
            return None
        challenges_data = campaign.meta.get("challenges", [])
        verifications_data = campaign.meta.get("verifications", [])
        sources = [extracted_source_from_dict(d) for d in extracted_data]
        challenges = [self._dict_to_challenge(d) for d in challenges_data]
        verifications = [self._dict_to_verification(d) for d in verifications_data]
        return sources, challenges, verifications

    def _build_report_and_brief(
        self,
        sources: list[Any],
        challenges: list[Any],
        verifications: list[Any],
        query: str,
    ) -> tuple[Any, str, list[Any]]:
        """Run the evaluation harness and render the insight brief."""
        report = self.eval_harness.evaluate(
            sources,
            challenges,
            verifications,
            query=query,
        )
        brief = self.reporter.to_markdown(
            report,
            sources=sources,
            challenges=challenges,
            verifications=verifications,
            query=query,
        )
        # When a synthesis lane is configured, produce a replication-grade brief
        # from the deep reads (unique-insight sources only). Fall back to the
        # deterministic reporter brief if synthesis is empty.
        if self.synthesizer is not None:
            # ReAct planner (#8): iterative gap-driven search co-evolving the
            # outline, banking far more evidence than the single discovery pass.
            # Uses its own bank+outline straight into the tuned section writer, so
            # nothing downstream changes. Falls through to the linear paths below
            # when the flag is off or the loop banks nothing.
            synthesized = self._react_brief(query)
            if synthesized.strip():
                brief = synthesized
                proposer = ImprovementProposer()
                return report, brief, proposer.propose(report)
            # Unverified claims must not reach the deliverable (grounding gate).
            source_dicts = unique_insight_filter(
                drop_failed_claims(
                    [extracted_source_to_dict(s) for s in sources], verifications
                )
            )
            if getattr(self, "writer_mode", "synth") == "attribute_first":
                # Phase 1.0 spike: attribute-first writing — each sentence is
                # generated FROM a verbatim evidence span and cites it, so the
                # citation is grounded by construction (vs post-hoc guarding).
                # Page-bound evidence: fetch each source's citable URL and mine
                # spans FROM that fetch, so every span is a verbatim substring of
                # the page a citation points to (verify-before-cite then passes by
                # construction). Falls back to abstract-mined spans when no browser
                # is available to fetch pages.
                if self.browser is not None:
                    # Page-bound evidence mines verbatim spans from each page
                    # directly, so it runs over ALL screened+readable sources — not
                    # the claim-filtered ``source_dicts`` (that filter drops sources
                    # lacking structured claims and would starve the bank). verify-
                    # before-cite below is the honesty gate; the claim filter is not.
                    bank = EvidenceBank.from_pages(
                        [extracted_source_to_dict(s) for s in sources],
                        self._fetch_page_text,
                        query,
                        max_fetches=len(sources) or 8,
                    )
                else:
                    bank = EvidenceBank.from_sources(source_dicts, query)
                # Outline-driven, section-by-section writing (WebWeaver) + WARP
                # deepening: the Planner organizes the bank's verified spans into a
                # structured outline; the Writer writes each section from ONLY its
                # evidence (carrying narrative context); then a deepening pass
                # diagnoses shallow sections and expands them from the bank. This
                # lifts comprehensiveness/depth/readability together (clean N=9
                # writer-eval: RACE 21.1 / E.Cit 14.6, best of 5 variants). Spans are
                # verbatim substrings of the cited page, so citations verify by
                # construction. Falls back to the flat writer if no outline forms.
                provider, wmodel = self.synthesizer.provider, self.synthesizer.model
                outline = OutlineBuilder(provider, wmodel).build(bank, query)
                # synthesis=True (#11): cohesive analytical paragraphs beat the choppy
                # one-span-per-sentence default on RACE, FACT, AND E.Cit (same-run cache
                # A/B: 28.31/49.3%/16.75 vs 27.13/45.0%/14.0). Promoted default writer.
                synthesized = SectionWriter(
                    provider, wmodel, carry_context=True, synthesis=True
                ).write(outline, bank, query)
                if synthesized.strip():
                    synthesized = deepen_report(synthesized, bank, query, provider, wmodel)
                if not synthesized.strip():
                    synthesized = AttributeFirstWriter(
                        self.synthesizer.provider, self.synthesizer.model
                    ).write(bank, query)
                if not synthesized.strip():
                    # No page-bound evidence (sources didn't fetch / abstract-only):
                    # fall back to legacy synthesis over the claim-filtered sources
                    # rather than the bare deterministic Reporter brief.
                    synthesized = self.synthesizer.synthesize(source_dicts, query)
            else:
                # Citations grounded against each source's own extract inside the
                # synthesizer. A re-fetch-based check was tried and removed:
                # lexical overlap on re-fetched boilerplate wrongly stripped
                # genuinely-supported HTML citations (measured FACT regression).
                synthesized = self.synthesizer.synthesize(source_dicts, query)
            if synthesized.strip():
                brief = synthesized
        proposer = ImprovementProposer()
        proposals = proposer.propose(report)
        return report, brief, proposals

    def _fetch_page_text(self, url: str) -> str:
        """Re-fetch a URL as markdownified text (same transform FACT uses)."""
        if self.browser is None:
            return ""
        raw = _resolve_byte_fetcher(self.browser)(url)
        return markdownify(raw[:200_000].decode("utf-8", errors="replace")).markdown[:6000]

    def _react_brief(self, query: str) -> str:
        """Run the ReAct planner and write its bank+outline; "" when off/empty."""
        _react_dbg(f"_react_brief: entry planner_mode={self.planner_mode!r}")
        result = self._react_plan(query)
        if result is None or self.synthesizer is None:
            _react_dbg(
                f"_react_brief: bailing result_is_none={result is None} "
                f"synth_is_none={self.synthesizer is None}"
            )
            return ""
        _react_dbg(
            f"_react_brief: plan OK spans={len(result.evidence_bank.spans())} "
            f"pages={result.pages_read} sections={len(result.outline.sections)}"
        )
        provider, model = self.synthesizer.provider, self.synthesizer.model
        max_sentences, max_tokens = _writer_length()
        draft = SectionWriter(
            provider,
            model,
            max_tokens=max_tokens,
            carry_context=True,
            synthesis=True,
            max_sentences=max_sentences,
        ).write(result.outline, result.evidence_bank, query)
        if not draft.strip():
            return ""
        return str(deepen_report(draft, result.evidence_bank, query, provider, model))

    def _react_plan(self, query: str) -> PlanResult | None:
        """Build + run the ReAct loop from the live components; None when unavailable.

        Requires the flag on and the agentic stack (browser to fetch, discovery to
        search, synthesizer's LLM to plan/summarise/outline). Returns None when the
        loop banks no evidence so the caller falls back cleanly.
        """
        if (
            self.planner_mode != "react"
            or self.browser is None
            or self.synthesizer is None
            or self.discovery is None
        ):
            _react_dbg(
                f"_react_plan: guard-None mode={self.planner_mode!r} "
                f"browser={self.browser is not None} synth={self.synthesizer is not None} "
                f"discovery={self.discovery is not None}"
            )
            return None
        provider, model = self.synthesizer.provider, self.synthesizer.model
        # Hybrid (docs/plan/hybrid_tongyi_plan.md): route the planner's REASONING seams
        # (objectives / refine / outline — and, for the spike, summarise to avoid
        # in-loop model swaps) to a trained deep-research model (e.g. Tongyi-DR Q4),
        # while search/read stay on our deterministic policy-guarded adapters. Unset ⇒
        # reasoning_model is the synth model ⇒ byte-identical to the single-model path.
        reasoning_model = os.environ.get("RESEARCH_ENGINE_REACT_REASONING_MODEL") or model
        discovery = self.discovery
        registry = getattr(discovery, "registry", None)
        serp_ok = registry is not None and "serp" in getattr(registry, "enabled", set())
        _react_dbg(
            f"_react_plan: serp_ok={serp_ok} enabled={sorted(getattr(registry, 'enabled', set()))} "
            f"reasoning_model={reasoning_model!r}"
        )
        _counts = {"search_calls": 0, "search_hits": 0, "read_calls": 0, "read_chars": 0}

        def _fetchable_ref(url: str | None, title: str) -> SourceRef | None:
            if not url:
                return None
            lu = url.lower()
            if lu.endswith(".pdf") or "doi.org" in lu:
                return None  # the fetcher/FACT cannot read these
            return SourceRef(url=url, title=title or "")

        def search_fn(sub_query: str) -> list[SourceRef]:
            # Lightweight serp-only search: SearXNG is already relevance-ranked, so we
            # skip the full discovery pipeline (academic APIs, snowball, resolve) AND
            # the per-candidate LLM ranker — running those per objective made react ~8x
            # too slow to finish (606 gemma calls/task, HANDOFF). Academic-only/test
            # envs fall back to the pipeline (still no LLM ranker).
            if serp_ok and registry is not None:
                found = registry.search("serp", sub_query, limit=_REACT_PER_QUERY)
                papers = list(found.papers) if found.ok else []
                _react_dbg(
                    f"search_fn: serp q={sub_query[:60]!r} ok={found.ok} papers={len(papers)}"
                )
            else:
                result = discovery.run(sub_query, context="", max_sources=_REACT_PER_QUERY)
                papers = [Paper.from_dict(g.canonical.to_dict()) for g in result.deduped_groups]
                _react_dbg(f"search_fn: discovery.run q={sub_query[:60]!r} papers={len(papers)}")
            refs = [r for p in papers if (r := _fetchable_ref(p.url or p.pdf_url, p.title))]
            _counts["search_calls"] += 1
            _counts["search_hits"] += len(refs)
            return refs

        def read_fn(ref: SourceRef) -> str:
            lu = ref.url.lower()
            if lu.endswith(".pdf") or "doi.org" in lu:
                return ""  # the fetcher/FACT cannot read these — don't spend budget on them
            try:
                self._validate_url(ref.url)
            except ValueError:
                _react_dbg(f"read_fn: url rejected {ref.url[:80]!r}")
                return ""
            try:
                text = self._fetch_page_text(ref.url)
                _counts["read_calls"] += 1
                _counts["read_chars"] += len(text)
                _react_dbg(f"read_fn: fetched {ref.url[:80]!r} chars={len(text)}")
                return text
            except Exception as exc:  # noqa: BLE001 — a failed fetch contributes nothing, not fatal
                _react_dbg(f"read_fn: fetch EXC {ref.url[:80]!r} {type(exc).__name__}: {exc}")
                return ""

        def _objectives(q: str) -> list[Any]:
            objs = plan_objectives(q, provider, reasoning_model)
            _react_dbg(f"objectives_fn: n={len(objs)} {[str(o)[:40] for o in objs][:6]}")
            return objs

        max_pages, per_objective, max_seconds = _react_budget()
        _react_dbg(
            f"_react_plan: budget max_pages={max_pages} per_obj={per_objective} "
            f"max_seconds={max_seconds}"
        )
        planner = ReactPlanner(
            objectives_fn=_objectives,
            search_fn=search_fn,
            read_fn=read_fn,
            summarize_fn=lambda q, obj, text: summarize_page(q, obj, text, provider, reasoning_model),
            refine_fn=lambda q, obj, digest: refine_query(q, obj, digest, provider, reasoning_model),
            outline_fn=lambda q, bank: OutlineBuilder(
                provider, reasoning_model, task_anchored=_react_anchored_outline()
            ).build(bank, q),
            max_pages=max_pages,
            per_objective_pages=per_objective,
            per_objective_searches=_react_per_objective_searches(),
            seeded_outline=_react_seeded_outline(),
            max_seconds=max_seconds,
        )
        result = planner.run(query)
        _react_dbg(
            f"_react_plan: DONE spans={len(result.evidence_bank.spans())} "
            f"pages={result.pages_read} iters={result.iterations} "
            f"search_calls={_counts['search_calls']} search_hits={_counts['search_hits']} "
            f"read_calls={_counts['read_calls']} read_chars={_counts['read_chars']}"
        )
        return result if result.evidence_bank.spans() else None

    def _build_deep_audit_payload(self, campaign: Campaign) -> dict[str, Any] | None:
        """Run the optional deep auditor and return a serializable payload."""
        if self.deep_auditor is None:
            return None
        audit_result = self.deep_auditor.audit(campaign.meta, trigger="evaluate")
        return {
            "anomalies": audit_result.anomalies,
            "recommendations": audit_result.recommendations,
            "raw_response": audit_result.raw_response,
        }

    def _build_evaluation_meta(
        self,
        campaign: Campaign,
        report: Any,
        brief: str,
        proposals: list[Any],
    ) -> Campaign:
        """Return a campaign updated with evaluation metadata."""
        return (
            campaign.with_meta("evaluation_report", {
                "total_claims": report.total_claims,
                "total_sources": report.total_sources,
                "challenged_count": report.challenged_count,
                "high_severity_count": report.high_severity_count,
                "verified_count": report.verified_count,
                "failed_verification_count": report.failed_verification_count,
                "citation_count": report.citation_count,
                "coverage_score": report.coverage_score,
                "quality_score": report.quality_score,
                "precision": report.precision,
                "recall": report.recall,
                "f1_score": report.f1_score,
                "meta": report.meta,
            })
            .with_meta("insight_brief", brief)
            .with_meta("improvement_proposals", proposals)
        )

    def _build_evaluation_result(
        self,
        report: Any,
        brief: str,
        proposals: list[Any],
        deep_audit_payload: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Assemble the stage result dictionary."""
        result: dict[str, Any] = {
            "ok": True,
            "coverage_score": report.coverage_score,
            "quality_score": report.quality_score,
            "precision": report.precision,
            "recall": report.recall,
            "f1_score": report.f1_score,
            "brief_length": len(brief),
            "proposal_count": len(proposals),
        }
        if deep_audit_payload is not None:
            result["deep_audit"] = deep_audit_payload
        return result

    def _run_deliver(self, campaign: Campaign) -> dict[str, Any]:
        """Write the insight brief to the host project's Research/ layout."""
        brief = campaign.meta.get("insight_brief", "")
        if not brief:
            return self._run_skipped(campaign, "no insight brief to deliver")
        insights_path = self.artifacts.write_campaign_brief(
            campaign.slug,
            brief,
            evidence_map={
                "campaign_id": campaign.id,
                "query": campaign.request.query,
                "stage": campaign.stage.value,
            },
        )
        existing = self.artifacts.list_campaign_briefs()
        master_path = self.artifacts.write_master_brief(existing)
        return {
            "ok": True,
            "brief_length": len(brief),
            "insights_path": str(insights_path),
            "master_path": str(master_path),
            "delivered": True,
        }

    def _dict_to_challenge(self, data: dict[str, Any]) -> Any:
        from research_engine.adversarial.challenge import Challenge
        return Challenge(
            claim_index=data.get("claim_index"),
            source_id=data.get("source_id"),
            claim_text=data.get("claim_text", ""),
            severity=data.get("severity", "low"),
            kind=data.get("kind", ""),
            reason=data.get("reason", ""),
            requested_evidence=data.get("requested_evidence", ""),
            resolved=data.get("resolved", False),
        )

    def _dict_to_verification(self, data: dict[str, Any]) -> Any:
        from research_engine.adversarial.challenge import VerificationResult
        return VerificationResult(
            claim_index=data.get("claim_index"),
            source_id=data.get("source_id"),
            claim_text=data.get("claim_text", ""),
            ok=data.get("ok", False),
            reason=data.get("reason", ""),
        )

    def _run_finalize(self, campaign: Campaign) -> dict[str, Any]:
        """Finalize a campaign: free the resident model, dedup files, vacuum DB."""
        # Release VRAM at session end (matches the "clear caches at end" vision).
        if self.lifecycle is not None and self.lifecycle.current:
            self.lifecycle.unload(self.lifecycle.current)
        now = datetime.now(UTC).isoformat()
        janitor = CleanupJanitor(
            self.store.db_path,
            engine_data_dir=self.config.engine_data_dir,
            project_root=self.config.project_root,
        )
        cleanup = janitor.clean()
        updated = (
            campaign.with_meta("finalized_at", now)
            .with_meta("cleanup_ok", cleanup.ok)
            .with_meta("cleanup_receipt", {
                "vacuumed_db": cleanup.vacuumed_db,
                "error": cleanup.error,
                "meta": cleanup.meta,
            })
        )
        self.store.update_campaign(updated)
        return {
            "ok": cleanup.ok,
            "finalized_at": now,
            "cleanup_ok": cleanup.ok,
            "cleanup_error": cleanup.error,
        }
