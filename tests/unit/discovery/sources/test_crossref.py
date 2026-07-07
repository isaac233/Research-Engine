"""Unit tests for the Crossref adapter."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import httpx

from research_engine.discovery.sources.crossref import CrossrefAdapter


def make_item(title: str, doi: str = "10.1234/example") -> dict[str, Any]:
    return {
        "title": [title],
        "author": [
            {"given": "Alice", "family": "Researcher"},
            {"given": "Bob", "family": "Scholar"},
        ],
        "published-print": {"date-parts": [[2024, 6]]},
        "DOI": doi,
        "abstract": "Example Crossref abstract.",
        "link": [{"URL": f"https://doi.org/{doi}"}],
    }


class FakeResponse:
    def __init__(self, status_code: int, json_data: dict[str, Any]) -> None:
        self.status_code = status_code
        self._json = json_data
        self.headers: dict[str, str] = {}

    @property
    def text(self) -> str:
        return json.dumps(self._json)

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")

    def json(self) -> dict[str, Any]:
        return self._json

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://api.crossref.org/"),
                response=httpx.Response(self.status_code),
            )


def test_search_parses_works() -> None:
    adapter = CrossrefAdapter()
    response = FakeResponse(200, {
        "message": {
            "total-results": 1,
            "items": [make_item("LLM alignment")],
        },
    })
    with patch("httpx.Client.request", return_value=response):
        result = adapter.search("LLM alignment")

    assert result.ok is True
    assert len(result.papers) == 1
    paper = result.papers[0]
    assert paper.title == "LLM alignment"
    assert paper.year == 2024
    assert paper.doi == "10.1234/example"
    assert paper.url == "https://doi.org/10.1234/example"
    assert len(paper.authors) == 2


def test_search_handles_http_error() -> None:
    adapter = CrossrefAdapter()
    response = FakeResponse(500, {})
    with patch("httpx.Client.request", return_value=response):
        result = adapter.search("LLM alignment")

    assert result.ok is False
    assert "HTTP" in (result.error or "")


def test_fetch_by_id_returns_paper() -> None:
    adapter = CrossrefAdapter()
    response = FakeResponse(200, {"message": make_item("Found by DOI")})
    with patch("httpx.Client.request", return_value=response):
        paper = adapter.fetch_by_id("10.1234/example")

    assert paper is not None
    assert paper.title == "Found by DOI"


def test_fetch_by_id_returns_none_on_error() -> None:
    adapter = CrossrefAdapter()
    response = FakeResponse(404, {})
    with patch("httpx.Client.request", return_value=response):
        paper = adapter.fetch_by_id("10.1234/missing")

    assert paper is None
