"""Render a benchmark summary into a Markdown scorecard vs the published bar."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from bench.leaderboard import (
    AS_OF,
    LEADERBOARD_URL,
    REFERENCE_BAR,
    SOURCE,
)

_DIMS = ("comprehensiveness", "insight", "instruction_following", "readability")
_DIM_LABEL = {
    "comprehensiveness": "Comp.",
    "insight": "Depth",
    "instruction_following": "Inst.",
    "readability": "Read.",
}


def _lowest_dimension(summary: dict[str, Any]) -> str:
    """Name the weakest RACE dimension — the Track B target."""
    scored = {d: summary.get(d, 0.0) for d in _DIMS}
    if not any(scored.values()):
        return "n/a (no scored tasks)"
    worst = min(scored, key=lambda d: scored[d])
    return f"{_DIM_LABEL[worst]} ({scored[worst]:.1f})"


def render(summary: dict[str, Any]) -> str:
    """Return the scorecard markdown for a benchmark summary."""
    lines: list[str] = []
    lines.append(f"# Research Engine — DeepResearch Bench Scorecard ({date.today().isoformat()})")
    lines.append("")
    lines.append(
        f"Judge: `{summary['judge']}` · Tasks: {summary['n_scored']}/{summary['n_tasks']} "
        f"scored ({summary.get('language') or 'all'} subset)"
    )
    lines.append("")
    lines.append("RACE is 0-100 where **50 = ties the reference report**. "
                 "FACT C.Acc = citation accuracy %, E.Cit = effective citations.")
    lines.append("")
    lines.append("| Model | RACE Overall | Comp. | Depth | Inst. | Read. | FACT C.Acc | E.Cit |")
    lines.append("|---|---|---|---|---|---|---|---|")
    lines.append(
        f"| **Research Engine (this run)** | **{summary['race_overall']:.2f}** | "
        f"{summary['comprehensiveness']:.2f} | {summary['insight']:.2f} | "
        f"{summary['instruction_following']:.2f} | {summary['readability']:.2f} | "
        f"{summary['fact_citation_accuracy']:.2f} | "
        f"{summary['fact_effective_citations']:.2f} |"
    )
    for ref in REFERENCE_BAR:
        lines.append(
            f"| {ref.name} | {ref.race_overall:.2f} | {ref.comprehensiveness:.2f} | "
            f"{ref.insight:.2f} | {ref.instruction_following:.2f} | {ref.readability:.2f} | "
            f"{ref.fact_c_acc:.2f} | {ref.fact_e_cit:.2f} |"
        )
    lines.append("")
    lines.append(f"**Weakest RACE dimension (Track B target):** {_lowest_dimension(summary)}")
    lines.append("")
    lines.append("## Notes")
    lines.append(f"- Reference bar: {SOURCE}, as of {AS_OF}.")
    lines.append(f"- Live leaderboard: {LEADERBOARD_URL}")
    lines.append(
        "- Judge caveat: if the local judge (Ollama) differs from the paper's "
        "Gemini-2.5-Pro judge, treat cross-rows as directional, not exact parity. "
        "Re-run with `--judge gemini` for the closest comparison."
    )
    lines.append("")
    return "\n".join(lines)


def write_scorecard(summary: dict[str, Any], project_root: Path | None = None) -> Path:
    """Write the scorecard to Research/benchmarks/<date>_scorecard.MD; return its path."""
    root = project_root or Path.cwd()
    out_dir = root / "Research" / "benchmarks"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{date.today().isoformat()}_scorecard.MD"
    path.write_text(render(summary), encoding="utf-8")
    return path
