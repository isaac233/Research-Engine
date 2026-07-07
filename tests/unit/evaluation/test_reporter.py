"""Unit tests for the evaluation reporter."""

from __future__ import annotations

from research_engine.adversarial.challenge import Challenge
from research_engine.discovery.schema import Paper
from research_engine.evaluation.harness import EvaluationHarness
from research_engine.evaluation.reporter import Reporter
from research_engine.extraction.structured import ExtractedClaim, ExtractedSource


def test_reporter_includes_summary_claims_and_challenges() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="Accuracy increased by 12%.",
        methodology="We ran a controlled experiment.",
        data_summary="1,000 samples.",
        results_summary="Accuracy increased by 12%.",
        claims=[
            ExtractedClaim(
                claim="We found that the new method improves accuracy by 12%.",
                evidence="Accuracy increased by 12%.",
                confidence="medium",
            )
        ],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    challenges = [Challenge(claim_text=source.claims[0].claim, severity="high", kind="missing_evidence", reason="no evidence")]
    report = EvaluationHarness().evaluate([source], challenges, [], query="test query")
    md = Reporter().to_markdown(report, sources=[source], challenges=challenges, query="test query")
    assert "Research Brief: test query" in md
    assert "Accuracy increased by 12%" in md
    assert "missing_evidence" in md
    assert "Caveats" in md
