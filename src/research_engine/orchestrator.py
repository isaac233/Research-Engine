"""Campaign orchestrator: state machine + lifecycle + pause/resume/kill."""

from __future__ import annotations

from typing import Any

from research_engine.events import EventBus
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

    def __init__(self, store: CampaignStore, event_bus: EventBus | None = None) -> None:
        self.store = store
        self.event_bus = event_bus or EventBus(store)

    def start_campaign(self, request: ResearchRequest) -> Campaign:
        """Create and persist a new campaign."""
        campaign = self.store.create_campaign(request)
        self.event_bus.emit(
            campaign.id,
            "stage_enter",
            {"stage": campaign.stage.value, "status": campaign.status.value},
        )
        return campaign

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
        return campaign

    def _set_status(self, campaign: Campaign, status: CampaignStatus) -> Campaign:
        updated = campaign.with_status(status)
        return self.store.update_campaign(updated)

    # --- Stage stubs: real work delegated to future subsystems. ---

    def _run_stub(self, campaign: Campaign) -> dict[str, Any]:
        """Placeholder for stages whose subsystems are not yet implemented."""
        return {"note": f"{campaign.stage.value} not yet implemented"}

    _run_init = _run_stub
    _run_plan = _run_stub
    _run_discover = _run_stub
    _run_screen = _run_stub
    _run_extract = _run_stub
    _run_adversarial = _run_stub
    _run_evaluate = _run_stub
    _run_deliver = _run_stub
    _run_finalize = _run_stub
