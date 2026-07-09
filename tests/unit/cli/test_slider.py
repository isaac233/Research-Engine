"""Unit tests for the constraint slider (non-interactive path)."""

from __future__ import annotations

from research_engine.cli.slider import prompt_constraints
from research_engine.planning.constraint_triangle import ConstraintInputs


def test_non_tty_returns_defaults_without_blocking() -> None:
    # pytest captures stdin -> not a TTY, so the slider must NOT prompt/hang.
    out = prompt_constraints(ConstraintInputs())
    assert out.quality == 0.5
    assert out.source_volume == 10


def test_non_tty_preserves_prefill() -> None:
    out = prompt_constraints(ConstraintInputs(quality=0.9, time_budget_s=300, source_volume=7))
    assert out.quality == 0.9
    assert out.time_budget_s == 300
    assert out.source_volume == 7
