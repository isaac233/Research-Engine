"""Unit tests for the minimum quality floor."""

from __future__ import annotations

from research_engine.planning.quality_floor import QualityFloor

_GOOD = [{"title": "A", "claims": [{"claim": "x improves y", "evidence": "we found x improves y"}]}]


def test_passes_with_evidenced_claim_and_brief() -> None:
    assert QualityFloor().check("An insight brief.", _GOOD).passed


def test_fails_on_empty_brief() -> None:
    result = QualityFloor().check("   ", _GOOD)
    assert not result.passed
    assert any("goal" in r for r in result.reasons)


def test_flags_omission_when_source_has_no_claims() -> None:
    result = QualityFloor().check("brief", [{"title": "B", "claims": []}])
    assert not result.passed
    assert result.omission


def test_flags_fabrication_when_claim_lacks_evidence() -> None:
    result = QualityFloor().check("brief", [{"title": "C", "claims": [{"claim": "z", "evidence": ""}]}])
    assert not result.passed
    assert result.fabrication


def test_reads_title_from_paper_when_missing_top_level() -> None:
    src = [{"paper": {"title": "P"}, "claims": []}]
    result = QualityFloor().check("brief", src)
    assert any("'P'" in r for r in result.reasons)
