"""Unit tests for the arXiv adapter."""

from __future__ import annotations

from unittest.mock import patch

import httpx

from research_engine.discovery.sources.arxiv import ArxivAdapter

ARXIV_FEED = """"<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>arxiv search</title>
  <opensearch:totalResults xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/">2</opensearch:totalResults>
  <entry>
    <title>LLM alignment via RLHF</title>
    <id>http://arxiv.org/abs/2401.00001</id>
    <published>2024-01-15T00:00:00Z</published>
    <summary>We study alignment.</summary>
    <author><name>Alice Researcher</name></author>
    <author><name>Bob Scholar</name></author>
    <arxiv:doi xmlns:arxiv="http://arxiv.org/schemas/atom">10.1234/example</arxiv:doi>
    <category term="cs.CL" />
  </entry>
  <entry>
    <title>Reward modeling</title>
    <id>http://arxiv.org/abs/2401.00002</id>
    <published>2023-08-10T00:00:00Z</published>
    <summary>Reward models.</summary>
    <author><name>Carol Author</name></author>
  </entry>
</feed>
"""


class FakeResponse:
    def __init__(self, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "error",
                request=httpx.Request("GET", "http://export.arxiv.org/"),
                response=httpx.Response(self.status_code),
            )


def test_search_parses_feed() -> None:
    adapter = ArxivAdapter()
    with patch("httpx.get", return_value=FakeResponse(200, ARXIV_FEED)):
        result = adapter.search("RLHF")

    assert result.ok is True
    assert len(result.papers) == 2
    paper = result.papers[0]
    assert paper.title == "LLM alignment via RLHF"
    assert paper.year == 2024
    assert paper.source_id == "2401.00001"
    assert paper.pdf_url == "https://arxiv.org/pdf/2401.00001.pdf"
    assert len(paper.authors) == 2


def test_search_handles_http_error() -> None:
    adapter = ArxivAdapter()
    with patch("httpx.get", return_value=FakeResponse(500, "")):
        result = adapter.search("RLHF")

    assert result.ok is False
    assert "HTTP" in (result.error or "")


def test_fetch_by_id_returns_paper() -> None:
    adapter = ArxivAdapter()
    feed = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Found by ID</title>
    <id>http://arxiv.org/abs/2401.00099</id>
    <published>2024-02-01T00:00:00Z</published>
    <summary>Abstract.</summary>
    <author><name>Alice</name></author>
  </entry>
</feed>
"""
    with patch("httpx.get", return_value=FakeResponse(200, feed)):
        paper = adapter.fetch_by_id("2401.00099")

    assert paper is not None
    assert paper.title == "Found by ID"


def test_fetch_by_id_returns_none_on_empty() -> None:
    adapter = ArxivAdapter()
    feed = """<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>"""
    with patch("httpx.get", return_value=FakeResponse(200, feed)):
        paper = adapter.fetch_by_id("missing")

    assert paper is None
