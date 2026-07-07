"""Campaign orchestrator: state machine + lifecycle + pause/resume/kill."""

from __future__ import annotations

from typing import Any

from research_engine.browser.ai_browser import AIBrowser
from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import Paper
from research_engine.events import EventBus
from research_engine.extraction.structured import StructuredExtractor, extracted_source_to_dict
from research_engine.screening.ranker import SourceRanker
from research_engine.state import (
    Campaign,
    CampaignStage,
    CampaignStatus,
    CampaignStore,
    ResearchRequest,
)


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
    ) -> None:
        self.store = store
        self.event_bus = event_bus or EventBus(store)
        self.browser = browser
        self.discovery = discovery
        self.ranker = ranker
        self.extractor = extractor

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
        return campaign

    def _execute_stage(self, campaign: Campaign, stage: CampaignStage) -> Campaign:
        handler_name = f"_run_{stage.value}"
        handler = getattr(self, handler_name, self._run_stub)
        result = handler(campaign)
        self.event_bus.emit(
            campaign.id,
            "stage_exit",
            {"stage": stage.value, "result": result},
        )
        return self._require_campaign(campaign.id)

    def _set_status(self, campaign: Campaign, status: CampaignStatus) -> Campaign:
        updated = campaign.with_status(status)
        return self.store.update_campaign(updated)

    # --- Stage stubs: real work delegated to future subsystems. ---

    def _run_stub(self, campaign: Campaign) -> dict[str, Any]:
        """Placeholder for stages whose subsystems are not yet implemented."""
        return {"note": f"{campaign.stage.value} not yet implemented"}

    _run_init = _run_stub
    _run_plan = _run_stub
    def _run_discover(self, campaign: Campaign) -> dict[str, Any]:
        """Dispatch discovery or unblocking probe depending on campaign type."""
        if campaign.meta.get("campaign_type") == "unblocking" and self.browser is not None:
            result = self.browser.unblock(campaign.request.query)
            return {
                "ok": result.ok,
                "action": result.action.value,
                "content_preview": result.content[:500] if result.content else "",
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
        extracted: list[dict[str, Any]] = []
        for paper_dict in included_data:
            paper = Paper.from_dict(paper_dict)
            source = self.extractor.extract(paper, content=paper.abstract, is_oa=paper.pdf_url is not None)
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

    _run_adversarial = _run_stub
    _run_evaluate = _run_stub
    _run_deliver = _run_stub
    _run_finalize = _run_stub
