"""Unit tests for the Semantic Scholar adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx

from research_engine.discovery.sources.semantic_scholar import SemanticScholarAdapter


def make_paper(title: str, paper_id: str = "s2-123") -> dict[str, Any]:
    return {
        "paperId": paper_id,
        "title": title,
        "authors": [{"name": "Alice Researcher"}, {"name": "Bob Scholar"}],
        "year": 2024,
        "abstract": "An example abstract.",
        "externalIds": {"DOI": "10.1234/example"},
        "openAccessPdf": {"url": "https://example.com/paper.pdf"},
        "citationCount": 42,
    }


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
                request=httpx.Request("GET", "https://api.semanticscholar.org/"),
                response=httpx.Response(self.status_code),
            )


def test_search_parses_papers() -> None:
    adapter = SemanticScholarAdapter()
    response = FakeResponse(200, {
        "total": 1,
        "data": [make_paper("LLM alignment")],
    })
    with patch("httpx.get", return_value=response):
        result = adapter.search("LLM alignment")

    assert result.ok is True
    assert len(result.papers) == 1
    paper = result.papers[0]
    assert paper.title == "LLM alignment"
    assert paper.year == 2024
    assert paper.doi == "10.1234/example"
    assert paper.pdf_url == "https://example.com/paper.pdf"
    assert paper.source == "semantic_scholar"
    assert paper.source_id == "s2-123"
    assert len(paper.authors) == 2


def test_search_handles_http_error() -> None:
    adapter = SemanticScholarAdapter()
    response = FakeResponse(500, {})
    with patch("httpx.get", return_value=response):
        result = adapter.search("LLM alignment")

    assert result.ok is False
    assert "HTTP" in (result.error or "")
    assert result.papers == []


def test_search_handles_request_error() -> None:
    adapter = SemanticScholarAdapter()
    with patch("httpx.get", side_effect=httpx.RequestError("network down")):
        result = adapter.search("LLM alignment")

    assert result.ok is False
    assert "network down" in (result.error or "")


def test_fetch_by_id_returns_paper() -> None:
    adapter = SemanticScholarAdapter()
    response = FakeResponse(200, make_paper("Found by ID", paper_id="s2-456"))
    with patch("httpx.get", return_value=response):
        paper = adapter.fetch_by_id("s2-456")

    assert paper is not None
    assert paper.title == "Found by ID"


def test_fetch_by_id_returns_none_on_error() -> None:
    adapter = SemanticScholarAdapter()
    response = FakeResponse(404, {})
    with patch("httpx.get", return_value=response):
        paper = adapter.fetch_by_id("missing")

    assert paper is None


def test_pagination_next_offset() -> None:
    adapter = SemanticScholarAdapter()
    response = FakeResponse(200, {
        "total": 25,
        "data": [make_paper(f"Paper {i}") for i in range(10)],
    })
    with patch("httpx.get", return_value=response):
        result = adapter.search("query", limit=10, offset=0)

    assert result.total == 25
    assert result.next_offset == 10
