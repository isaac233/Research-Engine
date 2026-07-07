"""Integration tests for discovery source adapters with mocked HTTP."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from research_engine.browser.ai_browser import (
    AIBrowser,
    BrowserAction,
    BrowserResult,
)
from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.arxiv import ArxivAdapter
from research_engine.discovery.sources.crossref import CrossrefAdapter
from research_engine.discovery.sources.openalex import OpenAlexAdapter
from research_engine.discovery.sources.semantic_scholar import SemanticScholarAdapter
from research_engine.discovery.sources.serp import SERPAdapter
from research_engine.discovery.sources.web_crawl import WebCrawlAdapter

pytestmark = pytest.mark.usefixtures("stub_public_dns")


class _FakeResponse:
    """Minimal httpx.Response stand-in for monkey-patched tests."""

    def __init__(self, text: str, status_code: int = 200) -> None:
        self._text = text
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    @property
    def text(self) -> str:
        return self._text

    @property
    def content(self) -> bytes:
        return self._text.encode("utf-8")

    def json(self) -> Any:
        return json.loads(self._text)

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "https://example.com"),
                response=self,  # type: ignore[arg-type]
            )


class _FakeBrowser(AIBrowser):
    """Browser stand-in that returns canned HTML."""

    name = "fake"

    def __init__(self, html: str) -> None:
        self.html = html

    def act(self, action: BrowserAction) -> BrowserResult:
        return BrowserResult(
            ok=True,
            action=action.action,
            url=action.url,
            status=200,
            content=self.html,
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True}


@pytest.fixture
def httpx_get(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Patch ``httpx.Client.request`` to return configured responses."""
    calls: dict[str, list[str]] = {"client_request": []}
    responses: dict[str, _FakeResponse] = {}

    def fake_client_request(
        self: httpx.Client,
        method: str,
        url: Any,
        **kwargs: Any,
    ) -> _FakeResponse:
        url_str = str(url)
        calls["client_request"].append(url_str)
        key = url_str.split("?")[0]
        if key in responses:
            return responses[key]
        for pattern, response in responses.items():
            if url_str.startswith(pattern):
                return response
        raise RuntimeError(f"Unexpected httpx.Client.request URL: {url_str}")

    monkeypatch.setattr(httpx.Client, "request", fake_client_request)
    return {"responses": responses, "calls": calls}


def _assert_paper_shape(result: SearchResult) -> None:
    assert result.ok
    assert result.papers
    paper = result.papers[0]
    assert isinstance(paper, Paper)
    assert paper.title
    assert paper.source


def test_semantic_scholar_search(httpx_get: dict[str, Any]) -> None:
    httpx_get["responses"]["https://api.semanticscholar.org/graph/v1/paper/search"] = _FakeResponse(
        json.dumps(
            {
                "total": 1,
                "data": [
                    {
                        "paperId": "s2paper",
                        "title": "Semantic Scholar Paper",
                        "authors": [{"name": "Alice Author"}],
                        "year": 2024,
                        "abstract": "An abstract.",
                        "externalIds": {"DOI": "10.1234/s2"},
                        "openAccessPdf": {"url": "https://pdf.example.com/s2.pdf"},
                        "citationCount": 42,
                    }
                ],
            }
        )
    )
    adapter = SemanticScholarAdapter()
    result = adapter.search("machine learning", limit=1)
    _assert_paper_shape(result)
    assert result.papers[0].doi == "10.1234/s2"
    assert result.papers[0].pdf_url == "https://pdf.example.com/s2.pdf"


def test_crossref_search(httpx_get: dict[str, Any]) -> None:
    httpx_get["responses"]["https://api.crossref.org/works"] = _FakeResponse(
        json.dumps(
            {
                "message": {
                    "items": [
                        {
                            "DOI": "10.1234/crossref",
                            "title": ["Crossref Paper"],
                            "author": [{"given": "Bob", "family": "Builder"}],
                            "created": {"date-parts": [[2023, 5, 1]]},
                            "link": [{"URL": "https://example.com/crossref"}],
                        }
                    ],
                    "total-results": 1,
                }
            }
        )
    )
    adapter = CrossrefAdapter(mailto="test@example.com")
    result = adapter.search("biology", limit=1)
    _assert_paper_shape(result)
    assert result.papers[0].doi == "10.1234/crossref"


def test_openalex_search(httpx_get: dict[str, Any]) -> None:
    httpx_get["responses"]["https://api.openalex.org/works"] = _FakeResponse(
        json.dumps(
            {
                "meta": {"count": 1},
                "results": [
                    {
                        "id": "https://openalex.org/W123",
                        "display_name": "OpenAlex Paper",
                        "publication_date": "2022-08-10",
                        "doi": "https://doi.org/10.1234/openalex",
                        "authorships": [{"author": {"display_name": "Carol C."}}],
                        "open_access": {"oa_url": "https://pdf.example.com/oa.pdf"},
                        "cited_by_count": 7,
                        "concepts": [{"display_name": "AI"}],
                    }
                ],
            }
        )
    )
    adapter = OpenAlexAdapter(mailto="test@example.com")
    result = adapter.search("artificial intelligence", limit=1)
    _assert_paper_shape(result)
    assert result.papers[0].doi == "10.1234/openalex"


def test_arxiv_search(httpx_get: dict[str, Any]) -> None:
    feed = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">
  <title>arxiv search</title>
  <opensearch:totalResults>1</opensearch:totalResults>
  <entry>
    <id>http://arxiv.org/abs/2401.00001</id>
    <title>arXiv Paper Title</title>
    <summary>An arxiv abstract.</summary>
    <published>2024-01-15T00:00:00Z</published>
    <author><name>Dan Researcher</name></author>
    <link href="http://arxiv.org/abs/2401.00001" rel="alternate"/>
  </entry>
</feed>
"""
    httpx_get["responses"]["https://export.arxiv.org/api/query"] = _FakeResponse(feed)
    adapter = ArxivAdapter()
    result = adapter.search("quantum", limit=1)
    _assert_paper_shape(result)
    assert result.papers[0].source_id == "2401.00001"
    assert result.papers[0].pdf_url == "https://arxiv.org/pdf/2401.00001.pdf"


def test_serp_search() -> None:
    html = (
        '<html><head><title>Search</title></head><body>'
        '<h2>Example Result</h2><a href="https://example.com/result">link</a>'
        '</body></html>'
    )
    adapter = SERPAdapter(endpoint="https://search.example.com/?q={query}", browser=_FakeBrowser(html))
    result = adapter.search("example query", limit=1)
    assert result.ok
    assert len(result.papers) == 1
    assert result.papers[0].url == "https://example.com/result"


def test_web_crawl_fetch_by_id() -> None:
    html = (
        '<html><head><title>Crawled Page</title></head>'
        '<body><p>Some useful content.</p></body></html>'
    )
    adapter = WebCrawlAdapter(browser=_FakeBrowser(html))
    paper = adapter.fetch_by_id("https://example.com/page")
    assert paper is not None
    assert paper.title == "Crawled Page"
    assert "useful content" in (paper.abstract or "")
