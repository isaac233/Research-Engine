"""Unit tests for the constraint-triangle solver."""

from __future__ import annotations

from research_engine.planning.constraint_triangle import (
    QUALITY_COST_S,
    SPEED_COST_S,
    ConstraintInputs,
    solve,
)


def test_none_given_needs_slider() -> None:
    plan = solve(ConstraintInputs())
    assert plan.needs_slider is True


def test_quality_only_needs_slider() -> None:
    # One non-time constraint is not enough to derive the rest.
    assert solve(ConstraintInputs(quality=0.8)).needs_slider is True


def test_time_only_auto_optimizes_no_slider() -> None:
    plan = solve(ConstraintInputs(time_budget_s=600))
    assert plan.needs_slider is False
    assert plan.time_budget_s == 600
    assert 0.0 <= plan.quality <= 1.0


def test_quality_plus_volume_derives_time() -> None:
    plan = solve(ConstraintInputs(quality=1.0, source_volume=5))
    assert plan.needs_slider is False
    assert plan.time_budget_s == int(5 * QUALITY_COST_S)


def test_quality_plus_time_derives_volume() -> None:
    # At speed cost, 10 sources fit in 10*SPEED_COST_S seconds.
    budget = int(10 * SPEED_COST_S)
    plan = solve(ConstraintInputs(quality=0.0, time_budget_s=budget))
    assert plan.source_volume == 10


def test_volume_plus_time_derives_quality() -> None:
    # Generous time for few sources -> higher quality; tight time -> lower.
    generous = solve(ConstraintInputs(time_budget_s=900, source_volume=10))
    tight = solve(ConstraintInputs(time_budget_s=90, source_volume=10))
    assert generous.quality > tight.quality


def test_quality_level_thresholds() -> None:
    assert solve(ConstraintInputs(quality=0.1, source_volume=1)).quality_level == "speed"
    assert solve(ConstraintInputs(quality=0.5, source_volume=1)).quality_level == "balanced"
    assert solve(ConstraintInputs(quality=0.9, source_volume=1)).quality_level == "quality"
    # lane assignment present for the tier
    assert solve(ConstraintInputs(quality=0.9, source_volume=1)).lane_assignment["extract"] == "deep"
