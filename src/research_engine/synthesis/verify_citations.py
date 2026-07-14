"""Verify-before-cite: keep only citations whose span is on the re-fetched page.

The FACT metric re-fetches every cited URL and checks support. This pass makes
the engine do the same before delivery: for each inline ``[eN]``, re-fetch the
span's URL the FACT way (markdownify), and strip the citation unless the span's
verbatim text is actually present on the page. Paywalled stubs, wrong URLs, and
writer drift are all dropped deterministically — every surviving citation
verifies. Prose is left intact; only unverifiable citation markers are removed.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from research_engine.memory.evidence_bank import EvidenceBank

_CITATION = re.compile(r"\[(e\d+)\]")
# Compare a leading window of the span so minor trailing differences don't fail a
# genuine on-page quote; long enough to be specific.
_SPAN_MATCH_CHARS = 80


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def verify_citations(
    brief: str,
    bank: EvidenceBank,
    fetch_fn: Callable[[str], str],
    *,
    max_urls: int = 25,
) -> str:
    """Strip ``[eN]`` whose span is not found on its re-fetched page."""
    if not brief:
        return brief
    marker = "\n## References"
    idx = brief.find(marker)
    body, references = (brief[:idx], brief[idx:]) if idx != -1 else (brief, "")

    page_cache: dict[str, str] = {}
    verdict: dict[str, bool] = {}

    def is_supported(span_id: str) -> bool:
        if span_id in verdict:
            return verdict[span_id]
        span = bank.get(span_id)
        if span is None or not span.url:
            verdict[span_id] = False
            return False
        if span.url not in page_cache:
            if len(page_cache) >= max_urls:
                verdict[span_id] = False
                return False
            try:
                page_cache[span.url] = _norm(fetch_fn(span.url))
            except Exception:  # noqa: BLE001 — a failed fetch cannot verify → strip
                page_cache[span.url] = ""
        needle = _norm(span.text)[:_SPAN_MATCH_CHARS].rstrip(".,;:!?- ")
        ok = bool(needle) and needle in page_cache[span.url]
        verdict[span_id] = ok
        return ok

    grounded = _CITATION.sub(
        lambda m: m.group(0) if is_supported(m.group(1)) else "", body
    )
    grounded = re.sub(r"[ \t]{2,}", " ", grounded)
    return grounded + references
