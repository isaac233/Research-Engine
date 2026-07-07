"""Web crawl adapter for non-academic pages."""

from __future__ import annotations

import re
from typing import Any

from research_engine.browser.ai_browser import AIBrowser, BrowserAction, BrowserActionType
from research_engine.browser.policy import URLPolicy
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.robots import RobotsChecker
from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.base import SourceAdapter


class WebCrawlAdapter(SourceAdapter):
    """Fetch and snapshot a web page as a non-academic source."""

    name = "web_crawl"
    default_limit = 5

    def __init__(
        self,
        browser: AIBrowser | None = None,
        robots: RobotsChecker | None = None,
        policy: URLPolicy | None = None,
    ) -> None:
        self.browser = browser or RawHTTPBrowser(policy=policy)
        self.robots = robots or RobotsChecker()

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        """Search here is a no-op; web crawl is URL-driven."""
        return SearchResult(
            source=self.name,
            query=query,
            error="WebCrawlAdapter requires explicit URLs; use fetch_by_id(url)",
        )

    def fetch_by_id(self, source_id: str) -> Paper | None:
        # source_id is a URL.
        robots_ok, robots_reason = self.robots.can_fetch(source_id)
        if not robots_ok:
            return None

        result = self.browser.act(
            BrowserAction(action=BrowserActionType.FETCH, url=source_id)
        )
        if not result.ok:
            return None

        title = self._extract_title(result.content)
        text = self._extract_text(result.content)
        return Paper(
            title=title or source_id,
            url=result.url or source_id,
            source=self.name,
            source_id=source_id,
            abstract=text[:1000],
            meta={
                "robots": robots_reason,
                "content_length": len(result.content),
                "text_length": len(text),
            },
        )

    def _extract_title(self, html: str) -> str | None:
        match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def _extract_text(self, html: str) -> str:
        """Very naive main-text extraction; Phase 4 will replace with markdownify."""
        # Drop scripts and styles.
        cleaned = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        cleaned = re.sub(r"<style[^>]*>.*?</style>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
        # Convert common block tags to newlines.
        cleaned = re.sub(r"</(p|div|h[1-6]|li)>", "\n", cleaned, flags=re.IGNORECASE)
        # Strip remaining tags.
        cleaned = re.sub(r"<[^>]+>", "", cleaned)
        # Collapse whitespace.
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": self.name}
