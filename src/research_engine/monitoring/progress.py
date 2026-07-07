"""Stage progress tracking for research campaigns."""

from __future__ import annotations

from research_engine.state import Campaign, CampaignStage


class StageProgressTracker:
    """Compute campaign progress and remaining stages."""

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

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        """Initialize with optional per-stage weights.

        Weights default to uniform (1.0) for every known stage. Missing stages
        in a custom weight dict still receive the default weight.
        """
        self.weights = {s.value: 1.0 for s in self.STAGE_ORDER}
        if weights:
            self.weights.update(weights)

    def progress_and_remaining(self, campaign: Campaign) -> tuple[int, list[str]]:
        """Return (progress percent 0-100, remaining stage values)."""
        current = campaign.stage.value
        try:
            index = self._stage_values.index(current)
        except ValueError:
            index = 0

        remaining = list(self._stage_values[index + 1 :])
        total_weight = sum(self.weights.values())
        if total_weight == 0:
            return 0, remaining

        completed_weight = sum(
            self.weights[s] for s in self._stage_values[: index + 1]
        )
        percent = int((completed_weight / total_weight) * 100)
        return min(100, max(0, percent)), remaining

    @property
    def _stage_values(self) -> list[str]:
        return [s.value for s in self.STAGE_ORDER]
