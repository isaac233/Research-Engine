"""Unit tests for the web crawl adapter."""

from __future__ import annotations

from research_engine.browser.ai_browser import BrowserAction, BrowserActionType, BrowserResult
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.robots import RobotsChecker
from research_engine.discovery.sources.web_crawl import WebCrawlAdapter


class FakeBrowser(RawHTTPBrowser):
    def __init__(self, html: str, ok: bool = True) -> None:
        self.html = html
        self.ok = ok

    def act(self, action: BrowserAction) -> BrowserResult:
        return BrowserResult(
            ok=self.ok,
            action=BrowserActionType.FETCH,
            url=action.url,
            status=200 if self.ok else 500,
            content=self.html,
        )


def test_search_returns_error() -> None:
    adapter = WebCrawlAdapter()
    result = adapter.search("anything")
    assert result.ok is False
    assert "url" in (result.error or "").lower()


def test_fetch_by_id_extracts_text() -> None:
    html = """
    <html><head><title>My Page</title></head>
    <body>
      <p>This is the main content.</p>
      <script>alert('ignored');</script>
    </body></html>
    """
    adapter = WebCrawlAdapter(browser=FakeBrowser(html))
    paper = adapter.fetch_by_id("https://example.com/page")
    assert paper is not None
    assert paper.title == "My Page"
    assert "main content" in paper.abstract
    assert "ignored" not in paper.abstract


def test_fetch_by_id_respects_robots() -> None:
    class DisallowRobots(RobotsChecker):
        def can_fetch(self, url: str, user_agent: str = "*") -> tuple[bool, str]:
            return False, "disallowed"

    adapter = WebCrawlAdapter(
        browser=FakeBrowser("html"),
        robots=DisallowRobots(),
    )
    paper = adapter.fetch_by_id("https://example.com/page")
    assert paper is None
