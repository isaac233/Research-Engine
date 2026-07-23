"""Interactive quality/speed + source-volume selection.

Shown only when the user gives fewer than two of {quality, time, volume} AND
the terminal is interactive. Uses an arrow-key list when prompt_toolkit is
installed, otherwise a numbered prompt. Never blocks a non-interactive run.
"""

from __future__ import annotations

import sys

import click

from research_engine.planning.constraint_triangle import ConstraintInputs

# Quality slider stops (label -> quality value).
_QUALITY_STOPS: list[tuple[str, float]] = [
    ("speed - one fast model, minimum acceptable quality", 0.15),
    ("balanced - fast screening + deep extraction", 0.5),
    ("quality - biggest models, many handoffs (slow)", 0.9),
]
_DEFAULT_VOLUME = 10


def _defaults(prefill: ConstraintInputs) -> ConstraintInputs:
    return ConstraintInputs(
        quality=prefill.quality if prefill.quality is not None else 0.5,
        time_budget_s=prefill.time_budget_s,
        source_volume=prefill.source_volume or _DEFAULT_VOLUME,
    )


def prompt_constraints(prefill: ConstraintInputs | None = None) -> ConstraintInputs:
    """Return constraints chosen by the user, or defaults if non-interactive.

    Never raises: a non-TTY, EOF, or aborted prompt falls back to balanced +
    default volume so a research run can't die on the slider.
    """
    prefill = prefill or ConstraintInputs()
    if not sys.stdin.isatty():
        return _defaults(prefill)
    try:
        quality = prefill.quality if prefill.quality is not None else _choose_quality()
        volume = prefill.source_volume or _choose_volume()
    except (click.Abort, EOFError):
        return _defaults(prefill)
    return ConstraintInputs(
        quality=quality, time_budget_s=prefill.time_budget_s, source_volume=volume
    )


def _choose_quality() -> float:
    arrow = _arrow_select(
        "Optimize for", [label for label, _ in _QUALITY_STOPS], default_index=1
    )
    if arrow is not None:
        return _QUALITY_STOPS[arrow][1]
    # Numbered fallback.
    click.echo("Optimize for quality vs speed:")
    for i, (label, _) in enumerate(_QUALITY_STOPS, start=1):
        click.echo(f"  {i}. {label}")
    choice = int(click.prompt("Choice", type=click.IntRange(1, len(_QUALITY_STOPS)), default=2))
    return _QUALITY_STOPS[choice - 1][1]


def _choose_volume() -> int:
    return int(
        click.prompt(
            "How many uniquely-useful sources to gather",
            type=click.IntRange(1, 200),
            default=_DEFAULT_VOLUME,
        )
    )


def _arrow_select(title: str, options: list[str], default_index: int = 0) -> int | None:
    """Arrow-key list via prompt_toolkit; None if unavailable so caller falls back."""
    try:
        from prompt_toolkit.shortcuts import radiolist_dialog
    except ImportError:
        return None
    try:
        result = radiolist_dialog(
            title=title,
            text="Use arrow keys, Enter to confirm:",
            values=[(i, label) for i, label in enumerate(options)],
            default=default_index,
        ).run()
    except Exception:  # noqa: BLE001 - any TUI failure -> numbered fallback
        return None
    return result if isinstance(result, int) else None
