"""Integration tests for the self-research script."""

from __future__ import annotations

from pathlib import Path

from scripts.self_research import run


def test_self_research_runs_and_captures_proposals(tmp_path: Path) -> None:
    result = run(
        "What reliability improvements should the Research Engine prioritize?",
        tmp_path,
    )

    assert result["paper_count"] >= 1
    assert 0.0 < result["elapsed_seconds"] < 30.0
    report = result["report"]
    assert "proposal_count" in report
    assert "coverage_score" in report
    assert "quality_score" in report
    assert "benchmark_proposal_count" in report
    assert "benchmark_utility_mean_f1" in report
    assert "benchmark_robustness_score" in report
    assert isinstance(report["benchmark_utility_mean_f1"], float)
    assert isinstance(report["benchmark_robustness_score"], float)
