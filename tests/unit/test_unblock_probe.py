"""Unit tests for the unblocking research probe."""

from __future__ import annotations

import json

from research_engine.browser.ai_browser import (
    BrowserAction,
    BrowserActionType,
    BrowserResult,
)
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.unblock_probe import UnblockProbe


class FakeHTTPBrowser(RawHTTPBrowser):
    def __init__(self, pages: dict[str, tuple[bool, str]]) -> None:
        self.pages = pages

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> BrowserResult:
        ok, content = self.pages.get(url, (False, ""))
        return BrowserResult(
            ok=ok,
            action=BrowserActionType.FETCH,
            url=url,
            status=200 if ok else None,
            content=content,
        )


def test_unsupported_action_returns_error() -> None:
    probe = UnblockProbe()
    result = probe.act(BrowserAction(action=BrowserActionType.FETCH))
    assert result.ok is False
    assert "only supports unblock" in (result.error or "").lower()


def test_empty_query_returns_error() -> None:
    probe = UnblockProbe()
    result = probe.act(BrowserAction(action=BrowserActionType.UNBLOCK))
    assert result.ok is False
    assert "query" in (result.error or "").lower()


def test_returns_candidates_when_pages_found() -> None:
    pages = {
        "https://www.google.com/search?q=free+data": (
            True,
            "<html><head><title>Google Search</title></head><body>results</body></html>",
        ),
        "https://duckduckgo.com/html/?q=free+data": (
            True,
            "<html><head><title>DuckDuckGo Search</title></head><body>results</body></html>",
        ),
    }
    probe = UnblockProbe(FakeHTTPBrowser(pages))
    result = probe.act(BrowserAction(action=BrowserActionType.UNBLOCK, query="free data"))
    assert result.ok is True
    data = json.loads(result.content)
    assert len(data) == 2
    assert result.meta["count"] == 2


def test_no_candidates_returns_evidence_log() -> None:
    pages: dict[str, tuple[bool, str]] = {}
    probe = UnblockProbe(FakeHTTPBrowser(pages))
    result = probe.act(BrowserAction(action=BrowserActionType.UNBLOCK, query="free data"))
    assert result.ok is False
    assert result.meta.get("query") == "free data"
    assert "searched" in result.meta
    assert "escalate" in (result.error or "").lower()
    assert json.loads(result.content)["candidates"] == []


def test_health_returns_ok() -> None:
    probe = UnblockProbe()
    health = probe.health()
    assert health["ok"] is True
    assert health["client"] == "unblock_probe"
