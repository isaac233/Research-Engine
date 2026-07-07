"""Unit tests for the evaluation harness."""

from __future__ import annotations

from research_engine.adversarial.challenge import Challenge, VerificationResult
from research_engine.discovery.schema import Paper
from research_engine.evaluation.harness import EvaluationHarness
from research_engine.extraction.citation import Citation
from research_engine.extraction.structured import ExtractedClaim, ExtractedSource


def _make_source() -> ExtractedSource:
    return ExtractedSource(
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
        citations=[Citation(raw="[1]", doi="10.1/1")],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )


def test_harness_computes_counts_and_scores() -> None:
    source = _make_source()
    harness = EvaluationHarness()
    report = harness.evaluate([source], [], [VerificationResult(ok=True)], query="q")
    assert report.total_sources == 1
    assert report.total_claims == 1
    assert report.citation_count == 1
    assert report.challenged_count == 0
    assert report.verified_count == 1
    assert report.coverage_score == 1.0
    assert report.quality_score == 1.0


def test_harness_penalizes_challenges_and_failures() -> None:
    source = _make_source()
    challenges = [Challenge(claim_text=source.claims[0].claim, severity="high", kind="missing_evidence", reason="test")]
    verifications = [VerificationResult(ok=False)]
    harness = EvaluationHarness()
    report = harness.evaluate([source], challenges, verifications, query="q")
    assert report.challenged_count == 1
    assert report.high_severity_count == 1
    assert report.failed_verification_count == 1
    assert report.quality_score < 1.0
