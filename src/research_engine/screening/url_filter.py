"""Fetchable-URL filter — bias the extraction budget toward pages that bank evidence.

The binding constraint on evidence volume is FETCHABILITY: academic candidates
(researchgate, publisher DOIs) pass relevance screening but 403/paywall on fetch,
yielding empty page-bound banks, while public HTML pages fetch clean. Relevance is
already LLM-judged upstream by the ranker, and fetchability is determined by host +
extension (a model can't predict a 403 from a URL better than a host rule can), so
this stage is a cheap, deterministic re-rank: within the relevance-passed set, float
likely-fetchable HTML above PDFs / DOIs / known paywalls *before* the source-count
cut, so the fetch/extract budget is spent on pages that actually yield evidence.

Deterministic (no extra LLM call) and stable (relevance order preserved within a
tier), so it never drops a source — a scarce-fetchable task keeps its DOIs as the
tail, where the extraction policy still tries the HTML landing page.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlsplit

# Hosts that reliably 403 bots or paywall the full text (abstract stub at best).
_PAYWALL_HOSTS = (
    "researchgate.net",
    "academia.edu",
    "sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "tandfonline.com",
    "jstor.org",
    "wiley.com",
    "onlinelibrary.wiley.com",
    "igi-global.com",
    "ieeexplore.ieee.org",
    "dl.acm.org",
    "ssrn.com",
)


def fetchability_score(url: str | None) -> int:
    """Rank how likely ``url`` yields readable HTML: 3 public > 2 doi > 1 pdf/paywall > 0 none."""
    if not url:
        return 0
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    path = urlsplit(url).path.lower()
    if host in ("doi.org", "dx.doi.org"):
        return 2  # redirects to publisher; sometimes an HTML landing page
    if path.endswith(".pdf") or any(host == h or host.endswith("." + h) for h in _PAYWALL_HOSTS):
        return 1  # the fetcher can't read PDFs; paywall hosts 403 bots
    return 3  # public HTML page — fetches clean


def prefer_fetchable[T](items: list[T], url_of: Callable[[T], str | None]) -> list[T]:
    """Stable-sort ``items`` so likely-fetchable URLs come first (relevance order kept)."""
    return sorted(items, key=lambda it: -fetchability_score(url_of(it)))
