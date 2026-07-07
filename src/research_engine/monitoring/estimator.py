"""Time-to-completion estimation for research campaigns."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from research_engine.monitoring.progress import StageProgressTracker
    from research_engine.state import Campaign, CampaignStore


class TimeEstimator:
    """Predict remaining campaign duration from historical stage timings."""

    DEFAULT_STAGE_SECONDS = 60

    def __init__(self, store: CampaignStore) -> None:
        self.store = store

    def predict_remaining(
        self,
        campaign: Campaign,
        progress_tracker: StageProgressTracker,
    ) -> tuple[int | None, str]:
        """Return estimated remaining seconds and a human-readable note."""
        percent, remaining = progress_tracker.progress_and_remaining(campaign)
        if not remaining:
            return 0, "No remaining stages"

        averages = self._average_stage_durations(campaign.id)
        total_seconds = 0.0
        history_stages: list[str] = []
        for stage in remaining:
            avg = averages.get(stage)
            if avg is not None:
                total_seconds += avg
                history_stages.append(stage)
            else:
                total_seconds += self.DEFAULT_STAGE_SECONDS

        if history_stages:
            note = (
                f"Estimated {len(remaining)} remaining stages "
                f"using history for {len(history_stages)} stage(s)"
            )
        else:
            note = (
                f"Estimated {len(remaining)} remaining stages "
                f"using conservative heuristics"
            )
        return int(total_seconds), note

    def _average_stage_durations(self, campaign_id: str) -> dict[str, float]:
        """Compute mean duration per completed stage for a campaign."""
        enter_events = {
            e["payload"].get("stage"): e
            for e in self.store.get_events(campaign_id, "stage_enter")
        }
        exit_events = {
            e["payload"].get("stage"): e
            for e in self.store.get_events(campaign_id, "stage_exit")
        }
        durations: dict[str, list[float]] = {}
        for stage, enter in enter_events.items():
            if stage is None:
                continue
            exit_event = exit_events.get(stage)
            if exit_event is None:
                continue
            try:
                dt_enter = datetime.fromisoformat(enter["timestamp"])
                dt_exit = datetime.fromisoformat(exit_event["timestamp"])
                delta = (dt_exit - dt_enter).total_seconds()
            except (ValueError, KeyError):
                continue
            if delta >= 0:
                durations.setdefault(stage, []).append(delta)

        return {
            stage: sum(values) / len(values) for stage, values in durations.items() if values
        }
