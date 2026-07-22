"""FACT scorer: citation trustworthiness (official-parity semantics).

Extract (fact, ref_idx, url) triplets from a report, dedupe, fetch each cited
URL, and judge support per statement. Mirrors the official DeepResearch Bench
pipeline (utils/scrape.py + validate.py + stat.py):

- fetch with up to 3 attempts (official scrape.py retries=3, 1s sleep);
- all statements citing one URL are judged in ONE batched call
  (validate.py groups per citation);
- three-way verdict supported/unsupported/unknown — an invalid page (or a
  citation whose judge call keeps failing) yields "unknown";
- ``citation_accuracy`` = supported / (supported + unsupported): official
  stat.py:27 EXCLUDES unknown from the denominator. ``citation_accuracy_all``
  keeps the legacy all-pairs denominator for continuity with older runs.

The official pipeline fetches via Jina Reader (renders JS, reads PDFs, passes
most bot walls); ``default_fetcher`` approximates that locally with the
policy-guarded raw fetcher, a lazy headless-CDP fallback for bot-blocked
pages, and PDF-to-text conversion.
"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from bench.fact_cache import FactFetchCache
from bench.judge import extract_json
from bench.prompts import FACT_EXTRACT_PROMPT, FACT_VALIDATE_PROMPT
from research_engine.browser.ai_browser import BrowserAction, BrowserActionType
from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.extraction.markdownify import markdownify
from research_engine.llm.provider import LLMProvider, Message

logger = logging.getLogger(__name__)

_MAX_URLS = 40  # ponytail: bound fetch cost per report; official has no cap
_MAX_CONTENT_CHARS = 12_000  # official passes the full Jina page; we cap for judge cost
_FETCH_ATTEMPTS = 3  # official scrape.py parity
_JUDGE_ATTEMPTS = 3  # official validate.py parity
_SCRAPE_FAILED = "scrape failed"
_VERDICTS = ("supported", "unsupported", "unknown")
# Constrain the batched verdict call for local judges (Ollama grammar); cloud
# judges ignore/honor it harmlessly.
_VALIDATE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {"idx": {"type": "integer"}, "result": {"type": "string"}},
        "required": ["idx", "result"],
    },
}


def _normalize_verdict(result: str) -> str:
    """Map judge phrasings onto the official 3-way verdict space.

    Cloud judges emit the schema's words; local judges drift to yes/true/no/
    false/neutral. Anything unrecognized is 'unknown' (excluded — never a
    free 'supported').
    """
    if result in _VERDICTS:
        return result
    if result in ("yes", "true", "support", "supported."):
        return "supported"
    if result in ("no", "false", "unsupport", "not supported", "unsupported."):
        return "unsupported"
    return "unknown"


def _cdp_enabled() -> bool:
    """CDP fallback for the judge fetcher; default ON (Jina-parity), '0' disables."""
    return os.environ.get("RESEARCH_ENGINE_BENCH_FACT_CDP", "1") != "0"


def default_fetcher(browser: RawHTTPBrowser | None = None) -> Callable[[str], str]:
    """Build a URL→text fetcher approximating the official Jina Reader.

    Raw policy-guarded HTTP first; on a failed/blocked/empty read, retry once
    through a lazy headless CDP browser (latched off when Chromium is absent).
    ``.pdf`` URLs are fetched as bytes and converted to text — the official
    Jina fetch reads PDFs, so PDF citations must be judgeable here too.
    """
    b = browser or RawHTTPBrowser()
    state: dict[str, Any] = {"cdp": None, "cdp_off": not _cdp_enabled()}

    def _cdp_fetch(url: str) -> str:
        if state["cdp_off"]:
            return ""
        if state["cdp"] is None:
            try:
                from research_engine.browser.cdp_driver import CDPDriver

                state["cdp"] = CDPDriver(
                    policy=b.policy, fingerprints=getattr(b, "fingerprints", None)
                )
            except Exception as exc:  # noqa: BLE001 — playwright missing
                logger.info("FACT cdp unavailable: %s", exc)
                state["cdp_off"] = True
                return ""
        try:
            result = state["cdp"].act(BrowserAction(action=BrowserActionType.FETCH, url=url))
        except Exception as exc:  # noqa: BLE001 — a failed recovery costs nothing extra
            logger.info("FACT cdp fetch failed %s: %s", url[:80], exc)
            return ""
        if not result.ok or not result.content:
            err = result.error or ""
            if "Executable" in err or "install" in err.lower():
                state["cdp_off"] = True  # no Chromium — stop relaunch-and-fail loops
            return ""
        return str(result.content)

    def _pdf_text(url: str) -> str:
        from research_engine.extraction.pdf_converter import PDFConverter

        try:
            raw = b.fetch_bytes(url)
        except Exception as exc:  # noqa: BLE001 — fetch layer already retried
            return f"{_SCRAPE_FAILED}: {exc}"
        try:
            result = PDFConverter().convert_bytes(raw)
            text = (result.markdown or "").strip()
        except Exception as exc:  # noqa: BLE001 — corrupt/unsupported PDF
            return f"{_SCRAPE_FAILED}: pdf convert error: {exc}"
        return text[:_MAX_CONTENT_CHARS] if text else f"{_SCRAPE_FAILED}: empty pdf text"

    def fetch(url: str) -> str:
        if url.split("?", 1)[0].split("#", 1)[0].lower().endswith(".pdf"):
            return _pdf_text(url)
        content = ""
        error = "no content"
        try:
            result = b.act(BrowserAction(action=BrowserActionType.FETCH, url=url))
            if result.ok and result.content and (result.status or 0) < 400:
                content = str(result.content)
            elif result.error:
                error = result.error
            elif not result.content:
                error = "no content"
            else:
                error = f"status {result.status}"
        except Exception as exc:  # noqa: BLE001 — policy/network failure → try CDP
            error = str(exc)
        if not content:
            content = _cdp_fetch(url)
        if not content:
            return f"{_SCRAPE_FAILED}: {error}"
        # Cap before markdownify so a multi-MB page never blows up the regex pass.
        content = content[: _MAX_CONTENT_CHARS * 8]
        if "<html" in content.lower() or "<body" in content.lower():
            content = markdownify(content).markdown
        return content[:_MAX_CONTENT_CHARS]

    def close() -> None:
        """Kill the lazy Chromium + HTTP client (mirror orchestrator._close_cdp)."""
        cdp = state.get("cdp")
        if cdp is not None:
            try:
                cdp.close()
            except Exception:  # noqa: BLE001
                pass
            state["cdp"] = None
        try:
            b.close()
        except Exception:  # noqa: BLE001
            pass

    fetch.close = close  # type: ignore[attr-defined]
    return fetch


def _fact_cache_path() -> str:
    return os.environ.get(
        "RESEARCH_ENGINE_BENCH_FACT_CACHE_PATH",
        str(Path(__file__).resolve().parents[1] / "data" / "cache.db"),
    )


def _maybe_cache_fetcher(base_fetch: Callable[[str], str]) -> Callable[[str], str]:
    """Wrap the judge fetcher with a record/replay cache when
    RESEARCH_ENGINE_BENCH_FACT_CACHE is set — each URL is fetched live at most once,
    so repeated same-task scoring stops rate-limiting hosts. Failures are not cached.
    Unset => the base fetcher unchanged (byte-identical default path).
    """
    if not os.environ.get("RESEARCH_ENGINE_BENCH_FACT_CACHE"):
        return base_fetch
    cache = FactFetchCache(_fact_cache_path())

    def cached(url: str) -> str:
        hit = cache.get(url)
        if hit is not None:
            return hit
        content = base_fetch(url)
        if content and not content.startswith(_SCRAPE_FAILED):
            cache.put(url, content)
        return content

    # Preserve the underlying fetcher's close (CDP release); FactScorer.close finds it.
    cached.close = getattr(base_fetch, "close", None) or (lambda: None)  # type: ignore[attr-defined]
    return cached


class FactScorer:
    """Score one article's citation trustworthiness (official-parity)."""

    def __init__(
        self,
        judge: LLMProvider,
        fetch_url: Callable[[str], str] | None = None,
        judge_model: str | None = None,
        max_urls: int = _MAX_URLS,
        retry_sleep: float = 1.0,
    ) -> None:
        self.judge = judge
        self.fetch_url = _maybe_cache_fetcher(fetch_url or default_fetcher())
        self.judge_model = judge_model
        self.max_urls = max_urls
        self.retry_sleep = retry_sleep

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

    def close(self) -> None:
        """Release the fetcher's browser resources (no-op for injected fetchers)."""
        closer = getattr(self.fetch_url, "close", None)
        if callable(closer):
            closer()

    def _fetch_with_retries(self, url: str) -> str:
        """Official scrape.py parity: up to 3 attempts, short sleep between.

        ponytail: this stacks on RawHTTPBrowser's internal transient retries and a
        CDP attempt — a permanently-dead URL costs a few extra seconds. Bounded by
        max_urls; tighten to transient-only detection if bench wall-clock matters.
        """
        content = f"{_SCRAPE_FAILED}: not fetched"
        for attempt in range(_FETCH_ATTEMPTS):
            content = self.fetch_url(url)
            if not content.startswith(_SCRAPE_FAILED):
                return content
            if attempt < _FETCH_ATTEMPTS - 1 and self.retry_sleep:
                time.sleep(self.retry_sleep)
        return content

    def _validate_url(self, content: str, facts: list[str]) -> list[str]:
        """Judge all statements citing one URL in a single batched call.

        Returns one verdict per fact. A judge call that keeps failing (bad JSON,
        wrong length) yields all-"unknown" — official validate.py records a
        ``validate_error`` and stat.py drops those citations from the metric.
        """
        statements = "\n".join(f"{i + 1}. {fact}" for i, fact in enumerate(facts))
        prompt = FACT_VALIDATE_PROMPT.format(reference=content, statements=statements)
        for attempt in range(_JUDGE_ATTEMPTS):
            try:
                raw = self.judge.complete(
                    [Message(role="user", content=prompt)],
                    model=self.judge_model,
                    temperature=0.0,
                    format=_VALIDATE_SCHEMA,
                )
                items = extract_json(raw)
                if not isinstance(items, list) or len(items) != len(facts):
                    raise ValueError(f"expected {len(facts)} verdicts, got {items!r:.120}")
                # Local judges emit 0-based idx when the schema says 1-based; detect
                # by presence of idx==0 and shift accordingly. Missing/broken idx
                # falls back to the item's position (the list is in statement order).
                idxs = [item.get("idx") for item in items if isinstance(item, dict)]
                base = 0 if any(i == 0 for i in idxs) else 1
                verdicts = ["unknown"] * len(facts)
                for pos, item in enumerate(items):
                    idx_raw = item.get("idx", item.get("index")) if isinstance(item, dict) else None
                    idx = int(idx_raw) - base if idx_raw is not None else pos
                    if not 0 <= idx < len(facts):
                        idx = pos
                    result = str(item.get("result", "")).strip().lower() if isinstance(item, dict) else ""
                    verdicts[idx] = _normalize_verdict(result)
                return verdicts
            except Exception as exc:  # noqa: BLE001
                logger.warning("FACT validate attempt %d failed: %s", attempt + 1, exc)
                if attempt < _JUDGE_ATTEMPTS - 1 and self.retry_sleep:
                    time.sleep(self.retry_sleep)
        return ["unknown"] * len(facts)

    def score(self, task_id: Any, article: str) -> dict[str, Any]:
        """Return per-article FACT metrics (official-parity accuracy + legacy view)."""
        pairs = self._extract_pairs(article)[: self.max_urls]
        counts = {"supported": 0, "unsupported": 0, "unknown": 0}
        if pairs:
            by_url: dict[str, list[str]] = {}
            for fact, url in pairs:
                by_url.setdefault(url, []).append(fact)
            for url, facts in by_url.items():
                content = self._fetch_with_retries(url)
                if content.startswith(_SCRAPE_FAILED):
                    counts["unknown"] += len(facts)
                    continue
                for verdict in self._validate_url(content, facts):
                    counts[verdict] += 1
        judged = counts["supported"] + counts["unsupported"]
        return {
            "id": task_id,
            "num_pairs": len(pairs),
            "num_supported": counts["supported"],
            "num_unsupported": counts["unsupported"],
            "num_unknown": counts["unknown"],
            "citation_accuracy": counts["supported"] / judged if judged else 0.0,
            "citation_accuracy_all": counts["supported"] / len(pairs) if pairs else 0.0,
            "effective_citations": counts["supported"],
        }
