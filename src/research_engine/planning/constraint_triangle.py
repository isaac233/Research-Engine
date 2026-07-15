"""Constraint triangle: {quality, time_budget, source_volume}.

Specifying any TWO derives the THIRD. A time budget always governs (no slider —
auto-optimize quality for the time). If fewer than two are given and there is no
time budget, the caller should show sliders (``needs_slider=True``).

The link between the three is a cost-per-source that rises with quality (higher
quality = bigger models + more handoffs). The default model is linear between a
fast floor and a quality ceiling; a calibrated cost function can be injected.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

# Candidate source cap. Kept ABOVE the ~20 sources a single-pass decomposition
# yields so the fetchable-URL filter (screening/url_filter) selects the fetchable
# top-N from a bigger pool instead of no-op'ing when pool ≈ cap (HANDOFF unlock).
DEFAULT_VOLUME = 40
# Seconds per source at the extremes (rough; overridable via cost_per_source).
SPEED_COST_S = 8.0
QUALITY_COST_S = 90.0


@dataclass(frozen=True, slots=True)
class ConstraintInputs:
    quality: float | None = None       # 0.0 (speed) .. 1.0 (max quality)
    time_budget_s: int | None = None
    source_volume: int | None = None


@dataclass(frozen=True, slots=True)
class ResolvedPlan:
    quality: float
    quality_level: str                  # "speed" | "balanced" | "quality"
    source_volume: int
    time_budget_s: int | None
    lane_assignment: dict[str, str] = field(default_factory=dict)
    needs_slider: bool = False
    note: str = ""


# Stage -> lane name by quality tier. Lane names resolve to real tags via the
# LaneRoster; kept decoupled here so the solver stays pure/testable.
_STAGE_LANES: dict[str, dict[str, str]] = {
    "speed": {"plan": "fast", "screen": "fast", "extract": "fast", "adversarial": "fast", "evaluate": "fast"},
    "balanced": {"plan": "online_a", "screen": "fast", "extract": "deep", "adversarial": "fast", "evaluate": "synth_a"},
    "quality": {"plan": "online_a", "screen": "fast", "extract": "deep", "adversarial": "overnight", "evaluate": "synth_a"},
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _quality_level(q: float) -> str:
    if q < 0.34:
        return "speed"
    if q < 0.67:
        return "balanced"
    return "quality"


def _cost(q: float, cost_per_source: Callable[[float], float] | None) -> float:
    if cost_per_source is not None:
        return max(cost_per_source(q), 0.1)
    return SPEED_COST_S + (QUALITY_COST_S - SPEED_COST_S) * _clamp01(q)


def _quality_from_cost(cost: float, cost_per_source: Callable[[float], float] | None) -> float:
    # Invert the default linear model; with a custom cost fn, binary-search.
    if cost_per_source is None:
        return _clamp01((cost - SPEED_COST_S) / (QUALITY_COST_S - SPEED_COST_S))
    lo, hi = 0.0, 1.0
    for _ in range(24):
        mid = (lo + hi) / 2
        if _cost(mid, cost_per_source) < cost:
            lo = mid
        else:
            hi = mid
    return _clamp01((lo + hi) / 2)


def solve(
    inputs: ConstraintInputs,
    cost_per_source: Callable[[float], float] | None = None,
    default_volume: int = DEFAULT_VOLUME,
) -> ResolvedPlan:
    """Resolve the triangle. See module docstring for the rules."""
    q, t, v = inputs.quality, inputs.time_budget_s, inputs.source_volume

    if t is not None:
        # Time governs: no slider.
        if v is not None and q is None:
            q = _quality_from_cost(t / max(v, 1), cost_per_source)
            note = "quality derived from time + volume"
        elif q is not None and v is None:
            v = max(1, int(t / _cost(q, cost_per_source)))
            note = "volume derived from time + quality"
        elif q is None and v is None:
            v = default_volume
            q = _quality_from_cost(t / v, cost_per_source)
            note = "quality auto-optimized for time budget"
        else:
            note = "all three provided; using as given"
        q = _clamp01(q if q is not None else 0.5)
        v = v if v is not None else default_volume
        return _plan(q, v, t, needs_slider=False, note=note)

    if q is not None and v is not None:
        t = int(v * _cost(q, cost_per_source))
        return _plan(_clamp01(q), v, t, needs_slider=False, note="time derived from quality + volume")

    # Fewer than two constraints and no time budget: caller shows sliders.
    return _plan(
        _clamp01(q if q is not None else 0.5),
        v if v is not None else default_volume,
        None,
        needs_slider=True,
        note="insufficient constraints; show sliders",
    )


def _plan(q: float, v: int, t: int | None, *, needs_slider: bool, note: str) -> ResolvedPlan:
    level = _quality_level(q)
    return ResolvedPlan(
        quality=round(q, 3),
        quality_level=level,
        source_volume=max(1, v),
        time_budget_s=t,
        lane_assignment=dict(_STAGE_LANES[level]),
        needs_slider=needs_slider,
        note=note,
    )


def _demo() -> None:
    # volume + time -> quality
    p = solve(ConstraintInputs(time_budget_s=200, source_volume=10))
    assert not p.needs_slider and 0.0 <= p.quality <= 1.0
    # quality + volume -> time
    p = solve(ConstraintInputs(quality=1.0, source_volume=10))
    assert p.time_budget_s == int(10 * QUALITY_COST_S)
    # quality + time -> volume
    p = solve(ConstraintInputs(quality=0.0, time_budget_s=80))
    assert p.source_volume == 10  # 80 / 8
    # nothing -> slider
    assert solve(ConstraintInputs()).needs_slider
    # time only -> no slider
    assert not solve(ConstraintInputs(time_budget_s=600)).needs_slider
    print("constraint_triangle demo ok")


if __name__ == "__main__":
    _demo()
