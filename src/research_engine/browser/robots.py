"""robots.txt parser and policy cache."""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urlparse

import httpx

from research_engine.browser.fingerprint import FingerprintRotator


class RobotsChecker:
    """Fetch, parse, and cache robots.txt per host."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._fingerprints = FingerprintRotator()

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

    def _fetch_robots(self, robots_url: str) -> urllib.robotparser.RobotFileParser | None:
        try:
            headers = self._fingerprints.next_headers()
            with httpx.Client(timeout=self.timeout, follow_redirects=True, headers=headers) as client:
                response = client.get(robots_url)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            parser = urllib.robotparser.RobotFileParser()
            parser.parse(response.text.splitlines())
            return parser
        except Exception:  # noqa: BLE001
            return None
