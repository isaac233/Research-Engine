"""Tests for stage weight calibration."""

from __future__ import annotations

from research_engine.monitoring.calibrator import Calibrator


def _events_for_stage(stage: str, duration_seconds: float) -> list[dict]:
    return [
        {
            "type": "stage_enter",
            "payload": {"stage": stage},
            "timestamp": "2026-07-06T00:00:00+00:00",
        },
        {
            "type": "stage_exit",
            "payload": {"stage": stage},
            "timestamp": f"2026-07-06T00:00:{duration_seconds:06.3f}+00:00",
        },
    ]


def test_calibrator_increases_weight_for_slow_stage() -> None:
    events = _events_for_stage("discover", 10.0) + _events_for_stage("screen", 2.0)
    calibrator = Calibrator()
    weights = calibrator.calibrate(events)
    assert weights["discover"] > weights["screen"]


def test_calibrator_normalizes_weights() -> None:
    events = _events_for_stage("init", 5.0) + _events_for_stage("plan", 5.0)
    calibrator = Calibrator()
    weights = calibrator.calibrate(events)
    total = sum(weights.values())
    assert round(total, 2) == 1.0
