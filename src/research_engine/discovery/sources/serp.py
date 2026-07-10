"""SERP / web search adapter for non-academic sources."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote_plus

from research_engine.browser.policy import URLPolicy
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.robots import RobotsChecker
from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.base import SourceAdapter


class SERPAdapter(SourceAdapter):
    """Generic web search adapter that calls a configured search endpoint.

    No hard-coded Google/Bing scraping is provided by default; the caller must
    supply an endpoint URL template such as a SearXNG instance or a paid API.
    """

    name = "serp"
    default_limit = 10

    def __init__(
        self,
        endpoint: str | None = None,
        browser: RawHTTPBrowser | None = None,
        robots: RobotsChecker | None = None,
        policy: URLPolicy | None = None,
        blocklist: tuple[str, ...] = (),
    ) -> None:
        self.endpoint = endpoint
        # URL substrings to drop from results (e.g. benchmark-dataset hosts
        # that leak the benchmark's own reference answers into discovery).
        self.blocklist = tuple(b.lower() for b in blocklist if b)
        # The configured endpoint is trusted operator infrastructure (often a
        # local SearXNG instance the default SSRF policy would block); trust
        # exactly that origin, nothing else.
        self._trusted_policy = (
            URLPolicy(trusted_origins=[endpoint]) if endpoint else None
        )
        if browser is None and policy is None:
            policy = self._trusted_policy
        self.browser = browser or RawHTTPBrowser(policy=policy, fingerprints=None)
        self.robots = robots or RobotsChecker(browser=self.browser)

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        limit = limit or self.default_limit
        if not self.endpoint:
            return SearchResult(
                source=self.name,
                query=query,
                error="No search endpoint configured. Set a SearXNG/API endpoint.",
            )

        url = self.endpoint.format(
            query=quote_plus(query),
            limit=int(limit),
            offset=int(offset),
        )
        if self._trusted_policy is not None and self._trusted_policy.is_trusted_origin(url):
            # Operator's own search instance: its robots.txt targets external
            # crawlers, not the operator. Result URLs are still robots-checked
            # by downstream fetchers.
            robots_reason = "trusted endpoint (robots skipped)"
        else:
            robots_ok, robots_reason = self.robots.can_fetch(url)
            if not robots_ok:
                return SearchResult(
                    source=self.name,
                    query=query,
                    error=f"robots.txt disallows: {robots_reason}",
                )

        result = self.browser.fetch(url)
        if not result.ok:
            return SearchResult(
                source=self.name,
                query=query,
                error=result.error or f"HTTP {result.status}",
            )

        papers = self._parse(result.content, limit)
        return SearchResult(
            source=self.name,
            query=query,
            papers=papers,
            total=len(papers),
            next_offset=None,
            meta={"robots": robots_reason, "endpoint": self.endpoint},
        )

    def fetch_by_id(self, source_id: str) -> Paper | None:
        # source_id is treated as a URL; fetch and snapshot.
        robots_ok, _ = self.robots.can_fetch(source_id)
        if not robots_ok:
            return None
        result = self.browser.fetch(source_id)
        if not result.ok:
            return None
        title = self._extract_title(result.content)
        return Paper(
            title=title or source_id,
            url=source_id,
            source=self.name,
            source_id=source_id,
            meta={"content_length": len(result.content)},
        )

    def _parse(self, body: str, limit: int) -> list[Paper]:
        """Parse a SearXNG-style JSON body if present, else fall back to HTML."""
        papers = self._parse_json(body, limit)
        if papers is not None:
            return papers
        return self._parse_html(body, limit)

    def _parse_json(self, body: str, limit: int) -> list[Paper] | None:
        """Parse SearXNG JSON: {"results":[{"title","url","content"}]}.

        Returns None (not []) when the body is not the expected JSON shape, so
        the caller can fall back to HTML scraping.
        """
        stripped = body.lstrip()
        if not stripped.startswith("{"):
            return None
        try:
            data = json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            return None
        results = data.get("results") if isinstance(data, dict) else None
        if not isinstance(results, list):
            return None
        papers: list[Paper] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            # SearXNG uses "url"; Whoogle's JSON uses "href".
            url = item.get("url") or item.get("href")
            title = item.get("title")
            if not url or not title:
                continue
            if self._blocked(str(url)):
                continue
            papers.append(
                Paper(
                    title=str(title).strip(),
                    url=str(url),
                    abstract=str(item.get("content", "")).strip(),
                    source=self.name,
                    source_id=str(url),
                    meta={"engine": item.get("engine", ""), "extracted": True},
                )
            )
            if len(papers) >= limit:
                break
        return papers

    def _parse_html(self, html: str, limit: int) -> list[Paper]:
        """Naive result extraction: finds title + link pairs."""
        papers: list[Paper] = []
        # Look for anchor tags with preceding heading or title tag.
        for match in re.finditer(
            r"(?:<h[123][^>]*>|\"title\"\s*:\s*\")([^<\"]+)(?:</h[123]|\").*?<a[^>]+href=\"(https?://[^\"]+)\"",
            html,
            re.IGNORECASE | re.DOTALL,
        ):
            title = match.group(1).strip()
            url = match.group(2)
            if self._blocked(url):
                continue
            papers.append(
                Paper(
                    title=title,
                    url=url,
                    source=self.name,
                    source_id=url,
                    meta={"extracted": True},
                )
            )
            if len(papers) >= limit:
                break
        return papers

    def _blocked(self, url: str) -> bool:
        lowered = url.lower()
        return any(fragment in lowered for fragment in self.blocklist)

    def _extract_title(self, html: str) -> str | None:
        match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None

    def health(self) -> dict[str, Any]:
        return {
            "ok": bool(self.endpoint),
            "source": self.name,
            "endpoint_configured": bool(self.endpoint),
        }
