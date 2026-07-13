"""Pre-screening snippet enrichment.

Web search adapters (SearXNG/SERP) return ~150-char snippets. The relevance
rubric then judges a thin snippet instead of the real page, and extraction has
nothing to work with. This module fetches the page for thin *web* sources and
replaces the snippet with a capped excerpt of the page text, so screening and
extraction both see real content. Academic sources (crossref/arxiv/openalex)
already carry real abstracts and are left untouched.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

from research_engine.browser.policy import URLPolicy
from research_engine.discovery.schema import Paper
from research_engine.extraction.markdownify import markdownify
from research_engine.screening.ranker import SNIPPET_TEXT_CHARS

# Sources whose "abstract" is really a search-result snippet worth expanding.
_WEB_SOURCES = frozenset({"serp", "web_crawl", "web"})

FetchFn = Callable[[str], bytes]


def enrich_snippets(
    papers: list[Paper],
    fetch_fn: FetchFn,
    *,
    policy: URLPolicy | None = None,
    max_fetches: int = 8,
    excerpt_chars: int = 2000,
) -> list[Paper]:
    """Return papers with thin web snippets replaced by page-text excerpts.

    Only web-source papers with a snippet-thin abstract and a policy-allowed URL
    are fetched, up to ``max_fetches``. Any fetch failure keeps the original
    paper unchanged. Non-web sources and already-readable papers are passed
    through without a network call.
    """
    policy = policy or URLPolicy()
    result: list[Paper] = []
    fetched = 0

    for paper in papers:
        if (
            fetched >= max_fetches
            or paper.source not in _WEB_SOURCES
            or not paper.url
            or len((paper.abstract or "").strip()) >= SNIPPET_TEXT_CHARS
            or not policy.allow(paper.url)[0]
        ):
            result.append(paper)
            continue

        try:
            html = fetch_fn(paper.url)
        except Exception:  # noqa: BLE001 — any fetch failure is non-fatal
            result.append(paper)
            continue

        fetched += 1
        excerpt = _page_excerpt(html, excerpt_chars)
        if not excerpt:
            result.append(paper)
            continue

        result.append(
            dataclasses.replace(
                paper,
                abstract=excerpt,
                meta={
                    **paper.meta,
                    "enriched_from_page": True,
                    "snippet": paper.abstract,
                },
            )
        )

    return result


def _page_excerpt(html: bytes, excerpt_chars: int) -> str:
    """Extract readable text from page HTML, capped at ``excerpt_chars``."""
    text = markdownify(html.decode("utf-8", errors="replace")).markdown.strip()
    return text[:excerpt_chars]
