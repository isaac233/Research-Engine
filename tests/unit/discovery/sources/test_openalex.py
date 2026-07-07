"""Unit tests for the OpenAlex adapter."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import httpx

from research_engine.discovery.sources.openalex import OpenAlexAdapter


def make_work(title: str, id_url: str = "https://openalex.org/W123") -> dict[str, Any]:
    return {
        "id": id_url,
        "display_name": title,
        "doi": "https://doi.org/10.1234/example",
        "publication_date": "2024-05-01",
        "authorships": [
            {"author": {"display_name": "Alice Researcher"}},
            {"author": {"display_name": "Bob Scholar"}},
        ],
        "abstract": "Example OpenAlex abstract.",
        "open_access": {"oa_url": "https://example.com/oa.pdf"},
        "cited_by_count": 7,
        "concepts": [{"display_name": "Machine Learning"}],
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
                request=httpx.Request("GET", "https://api.openalex.org/"),
                response=httpx.Response(self.status_code),
            )


def test_search_parses_works() -> None:
    adapter = OpenAlexAdapter()
    response = FakeResponse(200, {
        "meta": {"count": 1},
        "results": [make_work("LLM alignment")],
    })
    with patch("httpx.get", return_value=response):
        result = adapter.search("LLM alignment")

    assert result.ok is True
    assert len(result.papers) == 1
    paper = result.papers[0]
    assert paper.title == "LLM alignment"
    assert paper.year == 2024
    assert paper.doi == "10.1234/example"
    assert paper.pdf_url == "https://example.com/oa.pdf"
    assert len(paper.authors) == 2


def test_search_handles_http_error() -> None:
    adapter = OpenAlexAdapter()
    response = FakeResponse(500, {})
    with patch("httpx.get", return_value=response):
        result = adapter.search("LLM alignment")

    assert result.ok is False
    assert "HTTP" in (result.error or "")


def test_fetch_by_id_returns_paper() -> None:
    adapter = OpenAlexAdapter()
    response = FakeResponse(200, make_work("Found by ID"))
    with patch("httpx.get", return_value=response):
        paper = adapter.fetch_by_id("W123")

    assert paper is not None
    assert paper.title == "Found by ID"


def test_fetch_by_id_returns_none_on_error() -> None:
    adapter = OpenAlexAdapter()
    response = FakeResponse(404, {})
    with patch("httpx.get", return_value=response):
        paper = adapter.fetch_by_id("Wmissing")

    assert paper is None
