"""Browser-based unblocking research probe."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from research_engine.browser.ai_browser import (
    AIBrowser,
    BrowserAction,
    BrowserActionType,
    BrowserResult,
)
from research_engine.browser.raw_http import RawHTTPBrowser


@dataclass(frozen=True, slots=True)
class UnblockCandidate:
    """A candidate solution to a blocker."""

    title: str
    url: str
    source: str
    access_terms: str
    next_step: str
    confidence: str = "medium"
    caveats: list[str] = field(default_factory=list)


class UnblockProbe(AIBrowser):
    """Search public pages and APIs for concrete solutions to a blocker query."""

    name = "unblock_probe"

    def __init__(self, http_browser: RawHTTPBrowser | None = None) -> None:
        self.http = http_browser or RawHTTPBrowser()

    def act(self, action: BrowserAction) -> BrowserResult:
        if action.action != BrowserActionType.UNBLOCK:
            return BrowserResult(
                ok=False,
                action=action.action,
                url=None,
                status=None,
                content="",
                error="UnblockProbe only supports unblock actions",
            )
        query = action.query or ""
        if not query:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.UNBLOCK,
                url=None,
                status=None,
                content="",
                error="unblock requires query",
            )

        candidates = self.search(query)
        if not candidates:
            # The no-dead-ends contract says we must not claim "no solution" without evidence.
            # Return an empty list with a warning and the query so the caller can escalate.
            return BrowserResult(
                ok=False,
                action=BrowserActionType.UNBLOCK,
                url=None,
                status=None,
                content=json.dumps({"candidates": []}),
                meta={"query": query, "searched": self._search_urls(query)},
                error="No candidates found; escalate with evidence log",
            )

        return BrowserResult(
            ok=True,
            action=BrowserActionType.UNBLOCK,
            url=None,
            status=None,
            content=json.dumps(
                [self._candidate_to_dict(c) for c in candidates],
                indent=2,
            ),
            meta={"query": query, "count": len(candidates)},
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "client": "unblock_probe", "http": self.http.health()}

    def search(self, query: str) -> list[UnblockCandidate]:
        """Return ranked solution candidates for a blocker query."""
        # Phase 2 uses a minimal hard-coded/demo fallback. Phase 3 will wire real APIs.
        urls = self._search_urls(query)
        candidates: list[UnblockCandidate] = []
        for url in urls:
            result = self.http.fetch(url)
            if result.ok and result.content:
                title = self._extract_title(result.content)
                candidates.append(
                    UnblockCandidate(
                        title=title or f"Result from {url}",
                        url=url,
                        source=url,
                        access_terms="public web page",
                        next_step=f"Read {url} and extract relevant details.",
                        confidence="low" if not title else "medium",
                    )
                )
        return candidates

    def _search_urls(self, query: str) -> list[str]:
        """Generate candidate search URLs."""
        encoded = query.replace(" ", "+")
        return [
            f"https://www.google.com/search?q={encoded}",
            f"https://duckduckgo.com/html/?q={encoded}",
        ]

    def _extract_title(self, html: str) -> str | None:
        """Crude title extraction from HTML."""
        import re

        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        match = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
        return None

    def _candidate_to_dict(self, candidate: UnblockCandidate) -> dict[str, Any]:
        return {
            "title": candidate.title,
            "url": candidate.url,
            "source": candidate.source,
            "access_terms": candidate.access_terms,
            "next_step": candidate.next_step,
            "confidence": candidate.confidence,
            "caveats": list(candidate.caveats),
        }
