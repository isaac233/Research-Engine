"""Unit tests for the Verifier."""

from __future__ import annotations

from typing import Any

from research_engine.adversarial.verifier import Verifier
from research_engine.discovery.schema import Paper
from research_engine.extraction.structured import ExtractedClaim, ExtractedSource


class FakeHTTPClient:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def head(self, url: str) -> Any:
        class Response:
            status_code = 200 if self.ok else 500
        return Response()


def test_verifier_passes_when_evidence_in_source_text() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="Accuracy increased by 12%.",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[ExtractedClaim(claim="Accuracy increased.", evidence="Accuracy increased by 12%.", confidence="medium")],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    results = Verifier().verify([source])
    assert len(results) == 1
    assert results[0].ok is True


def test_verifier_fails_when_evidence_missing_from_text() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="10.1/1"),
        title="T",
        summary="",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[ExtractedClaim(claim="Accuracy increased.", evidence="Accuracy increased by 12%.", confidence="medium")],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    results = Verifier().verify([source])
    assert results[0].ok is False
    assert "not found" in results[0].reason


def test_verifier_flags_bad_doi_shape() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test", doi="not-a-doi"),
        title="T",
        summary="Accuracy increased by 12%.",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[ExtractedClaim(claim="Accuracy increased.", evidence="Accuracy increased by 12%.", confidence="medium")],
        citations=[],
        conflicts=[],
        full_text_url=None,
        is_oa=False,
        extraction_tool="test",
    )
    results = Verifier().verify([source])
    assert results[0].ok is False
    assert "DOI" in results[0].reason


def test_verifier_checks_url_reachability() -> None:
    source = ExtractedSource(
        paper=Paper(title="T", source="test"),
        title="T",
        summary="Accuracy increased by 12%.",
        methodology="",
        data_summary="",
        results_summary="",
        claims=[ExtractedClaim(claim="Accuracy increased.", evidence="Accuracy increased by 12%.", confidence="medium")],
        citations=[],
        conflicts=[],
        full_text_url="https://example.com/paper.pdf",
        is_oa=True,
        extraction_tool="test",
    )
    results = Verifier(http_client=FakeHTTPClient(ok=False)).verify([source])
    assert results[0].ok is False
    assert "URL" in results[0].reason
