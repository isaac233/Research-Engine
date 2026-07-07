"""Unit tests for the full-text resolver."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx

from research_engine.discovery.resolver import FullTextResolver
from research_engine.discovery.schema import Paper


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any]) -> None:
        self.status_code = status_code
        self._json = json_data

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://api.unpaywall.org/"),
                response=httpx.Response(self.status_code),
            )


def test_uses_adapter_pdf_url_first() -> None:
    resolver = FullTextResolver()
    paper = Paper(
        title="Direct PDF",
        source="test",
        source_id="id",
        pdf_url="https://example.com/direct.pdf",
    )
    result = resolver.resolve(paper)
    assert result.url == "https://example.com/direct.pdf"
    assert result.is_oa is True
    assert result.source == "adapter_pdf_url"


def test_resolves_arxiv_id() -> None:
    resolver = FullTextResolver()
    paper = Paper(
        title="arXiv paper",
        source="arxiv",
        source_id="2401.00001",
    )
    result = resolver.resolve(paper)
    assert result.url == "https://arxiv.org/pdf/2401.00001.pdf"
    assert result.is_oa is True
    assert result.source == "arxiv"


def test_resolves_via_unpaywall() -> None:
    resolver = FullTextResolver()
    paper = Paper(
        title="OA paper",
        doi="10.1234/example",
        source="crossref",
    )
    response = FakeResponse(200, {
        "doi": "10.1234/example",
        "is_oa": True,
        "best_oa_location": {
            "url": "https://oa.example.com/paper",
            "url_for_pdf": "https://oa.example.com/paper.pdf",
            "license": "cc-by",
            "version": "publishedVersion",
        },
    })
    with patch("httpx.get", return_value=response):
        result = resolver.resolve(paper)

    assert result.url == "https://oa.example.com/paper.pdf"
    assert result.is_oa is True
    assert result.source == "unpaywall"
    assert result.evidence.get("license") == "cc-by"


def test_falls_back_to_doi_landing_when_not_oa() -> None:
    resolver = FullTextResolver()
    paper = Paper(
        title="Closed paper",
        doi="10.1234/closed",
        source="crossref",
    )
    response = FakeResponse(200, {
        "doi": "10.1234/closed",
        "is_oa": False,
        "best_oa_location": None,
    })
    with patch("httpx.get", return_value=response):
        result = resolver.resolve(paper)

    assert result.url == "https://doi.org/10.1234/closed"
    assert result.is_oa is False
    assert result.source == "doi_landing"


def test_no_doi_or_pdf_returns_none() -> None:
    resolver = FullTextResolver()
    paper = Paper(title="No identifiers", source="test")
    result = resolver.resolve(paper)
    assert result.url is None
    assert result.is_oa is False
    assert result.source == "none"


def test_unpaywall_http_error_falls_back_to_doi() -> None:
    resolver = FullTextResolver()
    paper = Paper(
        title="Error paper",
        doi="10.1234/error",
        source="crossref",
    )
    response = FakeResponse(500, {})
    with patch("httpx.get", return_value=response):
        result = resolver.resolve(paper)

    # Unpaywall failure is non-fatal; we still have the DOI landing page.
    assert result.url == "https://doi.org/10.1234/error"
    assert result.is_oa is False
    assert result.source == "doi_landing"
