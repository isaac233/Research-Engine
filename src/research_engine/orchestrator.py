"""Campaign orchestrator: state machine + lifecycle + pause/resume/kill."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
from research_engine.discovery.query_planner import QueryPlanner
from research_engine.discovery.schema import Paper
from research_engine.evaluation.deep_audit import DeepAuditor
from research_engine.evaluation.harness import EvaluationHarness
from research_engine.evaluation.improvement import ImprovementProposer
from research_engine.evaluation.reporter import Reporter
from research_engine.events import EventBus
from research_engine.extraction.structured import (
    StructuredExtractor,
    extracted_source_from_dict,
    extracted_source_to_dict,
)
from research_engine.monitoring.estimator import TimeEstimator
from research_engine.monitoring.progress import StageProgressTracker
from research_engine.monitoring.telemetry import TelemetryAnalyzer, TelemetryEmitter
from research_engine.screening.ranker import SourceRanker
from research_engine.state import (
    Campaign,
    CampaignStage,
    CampaignStatus,
    CampaignStore,
    ResearchRequest,
)
from research_engine.storage.artifacts import ArtifactManager


class Orchestrator:
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
        return campaign

    def _execute_stage(self, campaign: Campaign, stage: CampaignStage) -> Campaign:
        handler_name = f"_run_{stage.value}"
        handler = getattr(self, handler_name, self._run_stub)
        try:
            result = handler(campaign)
        except Exception as exc:
            campaign = self._set_status(campaign, CampaignStatus.FAILED)
            self.event_bus.emit(
                campaign.id,
                "stage_failed",
                {"stage": stage.value, "error": str(exc)},
            )
            raise
        self.event_bus.emit(
            campaign.id,
            "stage_exit",
            {"stage": stage.value, "result": result},
        )
        self.telemetry_emitter.stage_transition(
            campaign.id,
            stage,
            campaign.status,
            {"stage": stage.value, "status": campaign.status.value},
        )
        self.telemetry_analyzer.check(campaign.id, self.store)
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
        return {
            "campaign_id": campaign.id,
            "stage": campaign.stage.value,
            "status": campaign.status.value,
            "progress_percent": progress_percent,
            "eta_seconds": eta_seconds,
            "remaining_stages": remaining_stages,
            "alerts": alerts,
        }

    # --- Stage stubs: real work delegated to future subsystems. ---

    def _run_stub(self, campaign: Campaign) -> dict[str, Any]:
        """Placeholder for stages whose subsystems are not yet implemented."""
        return {"note": f"{campaign.stage.value} not yet implemented"}

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
        if campaign.meta.get("campaign_type") == "unblocking" and self.browser is not None:
            result = self.browser.unblock(campaign.request.query)
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
                .with_meta("resolved_map", {k: {"url": r.url, "is_oa": r.is_oa, "source": r.source} for k, r in resolved_map.items()})
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
            return self._run_stub(campaign)
        papers = [Paper.from_dict(d) for d in canonical_data]
        scorecards = self.ranker.rank(papers, query=campaign.request.query)
        included = [s for s in scorecards if s.included][: campaign.request.max_sources]
        self.store.update_campaign(
            campaign.with_meta("scorecards", [self._scorecard_to_dict(s) for s in scorecards])
            .with_meta("included_papers", [s.paper.to_dict() for s in included])
        )
        return {
            "ok": True,
            "screened_count": len(scorecards),
            "included_count": len(included),
            "criteria_set": self.ranker.criteria.name,
        }

    def _run_extract(self, campaign: Campaign) -> dict[str, Any]:
        """Extract structured fields from included papers."""
        included_data = campaign.meta.get("included_papers", [])
        if not included_data or self.extractor is None:
            return self._run_stub(campaign)
        resolved_map = campaign.meta.get("resolved_map", {})
        fetch_fn = self.browser.fetch_bytes if self.browser is not None else None
        extracted: list[dict[str, Any]] = []
        for paper_dict in included_data:
            paper = Paper.from_dict(paper_dict)
            resolved = resolved_map.get(paper.key, {})
            content_url = resolved.get("url")
            is_oa = bool(resolved.get("is_oa", False))
            source = self.extractor.extract(
                paper,
                content=None,
                content_url=content_url,
                is_oa=is_oa,
                fetch_fn=fetch_fn,
            )
            extracted.append(extracted_source_to_dict(source))
        self.store.update_campaign(campaign.with_meta("extracted_sources", extracted))
        return {
            "ok": True,
            "extracted_count": len(extracted),
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
            return self._run_stub(campaign)
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

    def _run_evaluate(self, campaign: Campaign) -> dict[str, Any]:
        """Evaluate extracted output and produce a report."""
        inputs = self._load_evaluation_inputs(campaign)
        if inputs is None:
            return self._run_stub(campaign)
        sources, challenges, verifications = inputs
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
        proposer = ImprovementProposer()
        proposals = proposer.propose(report)
        return report, brief, proposals

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
            return self._run_stub(campaign)
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
        """Finalize a campaign: deduplicate files and vacuum state DB."""
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
