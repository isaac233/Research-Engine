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


def test_harness_scores_empty_expected_without_extracted_perfectly() -> None:
    harness = EvaluationHarness()
    report = harness.evaluate([], [], [], query="q")
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1_score == 1.0


def test_harness_scores_empty_expected_with_extracted_zero_precision() -> None:
    source = _make_source()
    harness = EvaluationHarness()
    report = harness.evaluate([source], [], [VerificationResult(ok=True)], query="q")
    assert report.precision == 0.0
    assert report.recall == 1.0
    assert report.f1_score == 0.0


def test_harness_computes_perfect_golden_scores() -> None:
    source = _make_source()
    harness = EvaluationHarness()
    expected = [source.claims[0].claim]
    report = harness.evaluate([source], [], [VerificationResult(ok=True)], query="q", expected_claims=expected)
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1_score == 1.0


def test_harness_computes_partial_golden_scores() -> None:
    source = _make_source()
    harness = EvaluationHarness()
    expected = ["the new method improves accuracy by 12%"]
    report = harness.evaluate([source], [], [VerificationResult(ok=True)], query="q", expected_claims=expected)
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.meta["matched_claim_count"] == 1


def test_harness_penalizes_missing_expected_claims() -> None:
    source = _make_source()
    harness = EvaluationHarness()
    expected = [source.claims[0].claim, "a second unrelated claim"]
    report = harness.evaluate([source], [], [VerificationResult(ok=True)], query="q", expected_claims=expected)
    assert report.precision == 1.0
    assert report.recall == 0.5
    assert report.f1_score == 0.6667


def test_harness_matches_paraphrased_claims() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[
            ExtractedClaim(
                claim="The proposed transformer model greatly exceeds the baseline performance.",
                evidence="",
                confidence="medium",
            )
        ],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    harness = EvaluationHarness()
    expected = ["The proposed transformer model surpasses the baseline by a wide margin."]
    report = harness.evaluate([source], [], [], query="q", expected_claims=expected)
    assert report.precision == 1.0
    assert report.recall == 1.0
    assert report.f1_score == 1.0
    assert report.meta["matched_claim_count"] == 1


def test_harness_rejects_opposite_negation_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "The proposed method is safe.",
        "The proposed method is not safe because it exposes user data.",
    )


def test_harness_rejects_opposite_direction_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "Accuracy increased after fine-tuning.",
        "Accuracy decreased after fine-tuning.",
    )


def test_harness_rejects_tautological_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "The proposed approach outperforms the baseline.",
        "The proposed approach is a proposed approach.",
    )


def test_harness_rejects_antonym_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "The proposed method is safe.",
        "The proposed method is unsafe.",
    )


def test_harness_rejects_hedged_substring_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "The method improves accuracy.",
        "The method improves accuracy only on synthetic data.",
    )


def test_harness_allows_both_qualified_claims() -> None:
    harness = EvaluationHarness()
    assert harness._claim_match(
        "The method improves accuracy mostly on synthetic data.",
        "The method improves accuracy only on synthetic data.",
    )


def test_harness_rejects_temporal_opposite_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "Accuracy improves after fine-tuning.",
        "Accuracy improves before fine-tuning.",
    )


def test_harness_rejects_numeric_mismatch_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "Accuracy improves by 12%.",
        "Accuracy improves by 5%.",
    )


def test_harness_rejects_comparative_operand_swap() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "Method A outperforms method B.",
        "Method B outperforms method A.",
    )
    assert not harness._claim_match(
        "Group X scored higher than group Y.",
        "Group Y scored higher than group X.",
    )


def test_harness_allows_benign_reorder_without_comparative() -> None:
    harness = EvaluationHarness()
    assert harness._claim_match(
        "The method improves accuracy and speed.",
        "The method improves speed and accuracy.",
    )


def test_harness_rejects_unit_mismatch_claims() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "The dose increased by 12 mg.",
        "The dose increased by 12 kg.",
    )


def test_harness_ignores_non_unit_words_after_numbers() -> None:
    harness = EvaluationHarness()
    assert harness._claim_match(
        "The study reports 12 improvements overall.",
        "The study reports 12 improvements.",
    )


def test_harness_treats_comma_formatted_numbers_as_equal() -> None:
    harness = EvaluationHarness()
    assert harness._claim_match(
        "The dataset contains 1,000 samples.",
        "The dataset contains 1000 samples.",
    )


def test_harness_rejects_causal_correlation_mismatch() -> None:
    harness = EvaluationHarness()
    assert not harness._claim_match(
        "Larger models cause higher accuracy.",
        "Larger models are correlated with higher accuracy.",
    )


def test_harness_allows_same_numeric_claims() -> None:
    harness = EvaluationHarness()
    assert harness._claim_match(
        "Accuracy improves by 12%.",
        "Accuracy improves by 12 percent.",
    )


def test_harness_allows_repeated_words_with_real_content() -> None:
    harness = EvaluationHarness()
    assert harness._claim_match(
        "The proposed approach outperforms the baseline.",
        "The proposed approach, a very effective approach, outperforms the baseline.",
    )


def test_harness_uses_maximum_bipartite_matching() -> None:
    harness = EvaluationHarness()
    extracted = ["a b c d e f", "a b c d"]
    expected = ["a b c d", "c d e f g"]
    assert harness._count_matches(extracted, expected) == 2


def test_harness_scores_tautology_as_false_positive() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[
            ExtractedClaim(
                claim="The proposed approach is a proposed approach.",
                evidence="",
                confidence="medium",
            )
        ],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    harness = EvaluationHarness()
    report = harness.evaluate(
        [source],
        [],
        [],
        query="q",
        expected_claims=["The proposed approach outperforms the baseline."],
    )
    assert report.precision == 0.0
    assert report.recall == 0.0
    assert report.f1_score == 0.0
    assert report.meta["matched_claim_count"] == 0
