"""robots.txt parser and policy cache."""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

from research_engine.browser.ai_browser import AIBrowser
from research_engine.browser.raw_http import RawHTTPBrowser


class RobotsChecker:
    """Fetch, parse, and cache robots.txt per host."""

    def __init__(self, browser: AIBrowser | None = None) -> None:
        self.browser = browser or RawHTTPBrowser()
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    def can_fetch(self, url: str, user_agent: str = "*") -> tuple[bool, str]:
        """Return (allowed, reason)."""
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False, "invalid URL"

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        parser = self._cache.get(robots_url)
        if parser is None:
            parser = self._fetch_robots(robots_url)
            if parser is None:
                return True, "no robots.txt found"
            self._cache[robots_url] = parser

        allowed = parser.can_fetch(user_agent, url)
        if allowed:
            return True, "robots.txt allows"
        return False, "robots.txt disallows"

    def _fetch_robots(
        self, robots_url: str
    ) -> urllib.robotparser.RobotFileParser | None:
        try:
            result = self.browser.fetch(robots_url)
            if not result.ok:
                return None
            if result.status == 404:
                return None
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(result.content.splitlines())
            return parser
        except Exception:  # noqa: BLE001
            return None
