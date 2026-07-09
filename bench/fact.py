"""FACT scorer: citation trustworthiness.

Extract (fact, ref_idx, url) triplets from a report, dedupe, fetch each cited
URL with the engine's own policy-guarded fetcher, and have the judge decide
whether the source supports the claim. Emits Citation Accuracy (% supported) and
Effective Citations (count of supported claims) per DeepResearch Bench FACT.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from bench.judge import extract_json
from bench.prompts import FACT_EXTRACT_PROMPT, FACT_SUPPORT_PROMPT
from research_engine.browser.ai_browser import BrowserAction, BrowserActionType
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.extraction.markdownify import markdownify
from research_engine.llm.provider import LLMProvider, Message

logger = logging.getLogger(__name__)

_MAX_URLS = 40  # ponytail: bound fetch cost per report; raise if reports cite more
_MAX_CONTENT_CHARS = 6000


def default_fetcher(browser: RawHTTPBrowser | None = None) -> Callable[[str], str]:
    """Build a URL→text fetcher using the engine's policy-guarded HTTP + markdownify."""
    b = browser or RawHTTPBrowser()

    def fetch(url: str) -> str:
        result = b.act(BrowserAction(action=BrowserActionType.FETCH, url=url))
        if not result.ok or not result.content:
            return f"scrape failed: {result.error or 'no content'}"
        content = result.content
        if "<html" in content.lower() or "<body" in content.lower():
            content = markdownify(content).markdown
        return content[:_MAX_CONTENT_CHARS]

    return fetch


class FactScorer:
    """Score one article's citation trustworthiness."""

    def __init__(
        self,
        judge: LLMProvider,
        fetch_url: Callable[[str], str] | None = None,
        judge_model: str | None = None,
        max_urls: int = _MAX_URLS,
    ) -> None:
        self.judge = judge
        self.fetch_url = fetch_url or default_fetcher()
        self.judge_model = judge_model
        self.max_urls = max_urls

    def _extract_pairs(self, article: str) -> list[tuple[str, str]]:
        """Return deduped (fact, url) pairs cited in the article."""
        try:
            raw = self.judge.complete(
                [Message(role="user", content=FACT_EXTRACT_PROMPT.format(report_text=article))],
                model=self.judge_model,
                temperature=0.0,
            )
            triplets = extract_json(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("FACT extraction failed: %s", exc)
            return []
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for t in triplets if isinstance(triplets, list) else []:
            if not isinstance(t, dict):
                continue
            fact = str(t.get("fact", "")).strip()
            url = str(t.get("url", "")).strip()
            if fact and url.startswith("http") and (fact, url) not in seen:
                seen.add((fact, url))
                pairs.append((fact, url))
        return pairs

    def _supported(self, fact: str, content: str) -> bool:
        try:
            raw = self.judge.complete(
                [
                    Message(
                        role="user",
                        content=FACT_SUPPORT_PROMPT.format(claim=fact, source_content=content),
                    )
                ],
                model=self.judge_model,
                temperature=0.0,
            )
            verdict = extract_json(raw)
            return bool(verdict.get("supported")) if isinstance(verdict, dict) else False
        except Exception as exc:  # noqa: BLE001
            logger.warning("FACT support check failed: %s", exc)
            return False

    def score(self, task_id: Any, article: str) -> dict[str, Any]:
        """Return {id, num_pairs, num_supported, citation_accuracy, effective_citations}."""
        pairs = self._extract_pairs(article)[: self.max_urls]
        if not pairs:
            return {
                "id": task_id,
                "num_pairs": 0,
                "num_supported": 0,
                "citation_accuracy": 0.0,
                "effective_citations": 0,
            }
        content_cache: dict[str, str] = {}
        supported = 0
        for fact, url in pairs:
            if url not in content_cache:
                content_cache[url] = self.fetch_url(url)
            content = content_cache[url]
            if not content.startswith("scrape failed") and self._supported(fact, content):
                supported += 1
        return {
            "id": task_id,
            "num_pairs": len(pairs),
            "num_supported": supported,
            "citation_accuracy": supported / len(pairs),
            "effective_citations": supported,
        }
