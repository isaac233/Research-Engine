"""Weight calibration for stage progress tracking using MAPE reduction."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from research_engine.monitoring.progress import StageProgressTracker


class Calibrator:
    """Adjust stage weights to reduce mean absolute percentage error (MAPE)."""

    def calibrate(
        self,
        events: list[dict[str, Any]],
        current_weights: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """Return adjusted stage weights from a completed campaign's events.

        The returned weights are normalized to sum to 1. Stages with no
        duration data keep their current weight (or the default uniform weight).
        """
        current_weights = dict(current_weights or {})
        defaults = {s.value: 1.0 for s in StageProgressTracker.STAGE_ORDER}
        weights = {**defaults, **current_weights}

        durations = self._stage_durations(events)
        if not durations:
            return self._normalize(weights)

        baseline = sum(durations.values()) / len(durations)
        if baseline <= 0:
            return self._normalize(weights)

        for stage, duration in durations.items():
            weights[stage] = max(0.1, duration / baseline)

        return self._normalize(weights)

    def _stage_durations(self, events: list[dict[str, Any]]) -> dict[str, float]:
        """Pair stage_enter/stage_exit events and compute durations."""
        enters: dict[str, dict[str, Any]] = {}
        durations: dict[str, list[float]] = {}
        for event in events:
            event_type = event.get("type")
            stage = event.get("payload", {}).get("stage")
            if stage is None:
                continue
            if event_type == "stage_enter":
                enters[stage] = event
            elif event_type == "stage_exit":
                enter = enters.get(stage)
                if enter is None:
                    continue
                try:
                    dt_enter = datetime.fromisoformat(enter["timestamp"])
                    dt_exit = datetime.fromisoformat(event["timestamp"])
                    delta = (dt_exit - dt_enter).total_seconds()
                except (ValueError, KeyError):
                    continue
                if delta >= 0:
                    durations.setdefault(stage, []).append(delta)

        return {
            stage: sum(values) / len(values) for stage, values in durations.items() if values
        }

    def _normalize(self, weights: dict[str, float]) -> dict[str, float]:
        total = sum(weights.values())
        if total == 0:
            return weights
        return {stage: round(weight / total, 4) for stage, weight in weights.items()}
