"""Scorecard rendering + lowest-dimension detection."""

from __future__ import annotations

from pathlib import Path

from bench.scorecard import render, write_scorecard

SUMMARY = {
    "judge": "ollama:qwen",
    "language": "en",
    "n_tasks": 3,
    "n_scored": 3,
    "race_overall": 41.0,
    "comprehensiveness": 44.0,
    "insight": 30.0,  # weakest
    "instruction_following": 49.0,
    "readability": 47.0,
    "fact_citation_accuracy": 80.0,
    "fact_effective_citations": 12.0,
    "per_task": [],
}


def test_render_has_engine_row_and_bar() -> None:
    md = render(SUMMARY)
    assert "Research Engine (this run)" in md
    assert "Claude-3.7-Sonnet w/Search" in md
    assert "Gemini-2.5-Pro Deep Research" in md


def test_render_flags_weakest_dimension() -> None:
    md = render(SUMMARY)
    assert "Depth (30.0)" in md  # insight is the paper's "Depth" column


def test_write_scorecard_creates_file(tmp_path: Path) -> None:
    path = write_scorecard(SUMMARY, project_root=tmp_path)
    assert path.exists()
    assert path.parent == tmp_path / "Research" / "benchmarks"
    assert "DeepResearch Bench Scorecard" in path.read_text(encoding="utf-8")
