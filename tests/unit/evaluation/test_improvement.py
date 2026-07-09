"""Tests for the improvement proposer."""

from __future__ import annotations

from research_engine.evaluation.harness import EvaluationReport
from research_engine.evaluation.improvement import ImprovementProposer


def test_proposer_flags_failed_verifications() -> None:
    report = EvaluationReport(
        total_claims=5,
        failed_verification_count=2,
        high_severity_count=0,
    )
    proposals = ImprovementProposer().propose(report)

    assert any(p["area"] == "verifier" for p in proposals)


def test_proposer_flags_high_severity_challenges() -> None:
    report = EvaluationReport(
        total_claims=5,
        failed_verification_count=0,
        high_severity_count=1,
    )
    proposals = ImprovementProposer().propose(report)

    assert any(p["area"] == "devil" for p in proposals)


def test_proposer_flags_missing_claims() -> None:
    report = EvaluationReport(total_claims=0)
    proposals = ImprovementProposer().propose(report)

    assert any(p["area"] == "extraction" for p in proposals)


def test_proposals_never_auto_apply() -> None:
    report = EvaluationReport(
        total_claims=0,
        failed_verification_count=1,
        high_severity_count=1,
    )
    proposals = ImprovementProposer().propose(report)

    assert all(p.get("auto_apply") is False for p in proposals)


def test_proposer_flags_low_f1() -> None:
    report = EvaluationReport(total_claims=2, f1_score=0.5)
    proposals = ImprovementProposer().propose(report)
    assert any(p["area"] == "evaluation" and "F1" in p["issue"] for p in proposals)


def test_proposer_flags_missing_golden_claims() -> None:
    report = EvaluationReport(total_claims=1, meta={"expected_claim_count": 0})
    proposals = ImprovementProposer().propose(report)
    assert any(
        p["area"] == "evaluation" and "golden-answer" in p["suggested_action"]
        for p in proposals
    )


def test_proposer_flags_saturated_benchmark() -> None:
    report = EvaluationReport(
        total_claims=2,
        f1_score=1.0,
        meta={"expected_claim_count": 2},
    )
    proposals = ImprovementProposer().propose(report)
    assert any(p["area"] == "evaluation" and "saturated" in p["issue"] for p in proposals)
