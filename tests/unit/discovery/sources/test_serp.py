"""Unit tests for the SERP adapter."""

from __future__ import annotations

from research_engine.browser.ai_browser import BrowserAction, BrowserActionType, BrowserResult
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.robots import RobotsChecker
from research_engine.discovery.sources.serp import SERPAdapter


class FakeBrowser(RawHTTPBrowser):
    def __init__(self, html: str, ok: bool = True, error: str | None = None) -> None:
        self.html = html
        self.ok = ok
        self.error = error

    def act(self, action: BrowserAction) -> BrowserResult:
        return BrowserResult(
            ok=self.ok,
            action=BrowserActionType.FETCH,
            url=action.url,
            status=200 if self.ok else 500,
            content=self.html,
            error=self.error,
        )


def test_missing_endpoint_returns_error() -> None:
    adapter = SERPAdapter()
    result = adapter.search("free dataset")
    assert result.ok is False
    assert "endpoint" in (result.error or "").lower()


def test_robots_disallow_blocks() -> None:
    class DisallowRobots(RobotsChecker):
        def can_fetch(self, url: str, user_agent: str = "*") -> tuple[bool, str]:
            return False, "disallowed"

    adapter = SERPAdapter(
        endpoint="https://search.example/?q={query}",
        browser=FakeBrowser(""),
        robots=DisallowRobots(),
    )
    result = adapter.search("query")
    assert result.ok is False
    assert "robots" in (result.error or "").lower()


def test_parses_results_from_html() -> None:
    html = """
    <h2>Result One</h2>
    <a href="https://example.com/one">link</a>
    <h3>Result Two</h3>
    <a href="https://example.com/two">link</a>
    """
    adapter = SERPAdapter(
        endpoint="https://search.example/?q={query}",
        browser=FakeBrowser(html),
    )
    result = adapter.search("query")
    assert result.ok is True
    assert len(result.papers) == 2
    assert result.papers[0].title == "Result One"
    assert result.papers[0].url == "https://example.com/one"


def test_fetch_by_id_snapshots_page() -> None:
    html = "<html><head><title>Page Title</title></head><body>...</body></html>"
    adapter = SERPAdapter(
        endpoint="https://search.example/?q={query}",
        browser=FakeBrowser(html),
    )
    paper = adapter.fetch_by_id("https://example.com/page")
    assert paper is not None
    assert paper.title == "Page Title"
    assert paper.source_id == "https://example.com/page"


def test_health_requires_endpoint() -> None:
    adapter = SERPAdapter()
    health = adapter.health()
    assert health["ok"] is False
    assert health["endpoint_configured"] is False


def test_parses_searxng_json() -> None:
    """SearXNG /search?format=json returns {results:[{title,url,content}]}."""
    payload = (
        '{"query":"q","number_of_results":2,"results":['
        '{"url":"https://a.test/1","title":"First Hit","content":"snippet one","engine":"google"},'
        '{"url":"https://b.test/2","title":"Second Hit","content":"snippet two","engine":"bing"}]}'
    )
    adapter = SERPAdapter(
        endpoint="http://localhost:8080/search?q={query}&format=json",
        browser=FakeBrowser(payload),
    )
    result = adapter.search("q")
    assert result.ok is True
    assert len(result.papers) == 2
    assert result.papers[0].title == "First Hit"
    assert result.papers[0].url == "https://a.test/1"
    assert result.papers[0].abstract == "snippet one"
    assert result.papers[0].source == "serp"


def test_searxng_json_respects_limit() -> None:
    payload = (
        '{"results":['
        '{"url":"https://a.test/1","title":"A","content":"x"},'
        '{"url":"https://a.test/2","title":"B","content":"y"},'
        '{"url":"https://a.test/3","title":"C","content":"z"}]}'
    )
    adapter = SERPAdapter(endpoint="http://localhost:8080/search?q={query}&format=json",
                          browser=FakeBrowser(payload))
    result = adapter.search("q", limit=2)
    assert len(result.papers) == 2


def test_non_json_still_parses_as_html() -> None:
    """A malformed/HTML body must not crash; falls back to the HTML parser."""
    html = '<h3>Only Hit</h3> <a href="https://c.test/1">link</a>'
    adapter = SERPAdapter(endpoint="https://search.example/?q={query}",
                          browser=FakeBrowser(html))
    result = adapter.search("q")
    assert result.ok is True
    assert result.papers[0].url == "https://c.test/1"
