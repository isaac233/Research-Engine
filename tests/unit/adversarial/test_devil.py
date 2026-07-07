"""Unit tests for the Devil adversarial agent."""

from __future__ import annotations

from research_engine.adversarial.devil import DevilAgent
from research_engine.discovery.schema import Paper
from research_engine.extraction.structured import ExtractedClaim, ExtractedSource


def test_devil_flags_missing_evidence() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[ExtractedClaim(claim="The method works.", evidence="", confidence="medium")],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    challenges = DevilAgent().challenge([source])
    assert any(c.kind == "missing_evidence" and c.severity == "high" for c in challenges)


def test_devil_flags_low_confidence() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[
            ExtractedClaim(
                claim="We found that the method improves accuracy by twelve percent in the test set.",
                evidence="We found that the method improves accuracy by twelve percent in the test set.",
                confidence="low",
            )
        ],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    challenges = DevilAgent().challenge([source])
    assert any(c.kind == "low_confidence" and c.severity == "medium" for c in challenges)


def test_devil_flags_missing_source() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[
            ExtractedClaim(
                claim="We found that the method improves accuracy by twelve percent in the test set.",
                evidence="We found that the method improves accuracy by twelve percent in the test set.",
                confidence="medium",
            )
        ],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    challenges = DevilAgent().challenge([source])
    assert any(c.kind == "missing_source" and c.severity == "high" for c in challenges)


def test_devil_flags_short_claim_coverage() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[ExtractedClaim(claim="It works well.", evidence="It works well.", confidence="medium")],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    challenges = DevilAgent().challenge([source])
    assert any(c.kind == "coverage" and c.severity == "low" for c in challenges)
