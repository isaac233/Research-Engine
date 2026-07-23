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
from research_engine.synthesis.minicheck import CheckFn

_CITATION = re.compile(r"\[(e\d+)\]")
# Compare a leading window of the span so minor trailing differences don't fail a
# genuine on-page quote; long enough to be specific.
_SPAN_MATCH_CHARS = 80


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _sentence_spans(body: str) -> list[tuple[int, int]]:
    """(start, end) offsets of each sentence, robust to citation markers.

    A boundary is a ``.!?`` or newline that — after skipping any citation markers glued
    directly to it (``2024.[e1] Next``) — is followed by whitespace or end-of-text. This
    keeps a trailing ``[eN]`` inside the sentence it cites (so the marker is attributed to
    the right claim) and does not split decimals like ``3.5%``. A regex split on
    ``[.!?](?=\\s|$)`` alone silently fails on ``claim.[e1]`` — dropping supported cites.
    """
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "\n":
            spans.append((start, i + 1))
            start = i + 1
            i += 1
            continue
        if ch in ".!?":
            j = i + 1
            while j < n and body[j] == "[":  # absorb markers glued after the terminator
                close = body.find("]", j)
                if close == -1 or not _CITATION.match(body[j : close + 1]):
                    break
                j = close + 1
            if j >= n or body[j].isspace():
                spans.append((start, j))
                start = j
                i = j
                continue
        i += 1
    if start < n:
        spans.append((start, n))
    return spans


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


def abstain_citations(
    brief: str,
    bank: EvidenceBank,
    page_text_fn: Callable[[str], str],
    check_fn: CheckFn,
    *,
    tau: float = 0.5,
    max_checks: int = 200,
) -> str:
    """Drop each ``[eN]`` whose enclosing sentence isn't supported by the span's page.

    Attribute-or-abstain (W1): a small grounded fact-checker (MiniCheck) scores the cited
    sentence against the FULL page the span came from — the same granularity the FACT
    metric uses — and the marker is removed when support < ``tau``. The prose is left
    intact; only the citation marker is softened, so an over-confident thin bank stops
    producing unsupported *cited* claims (task 53: 76 markers, 13 verified). Deterministic
    and bounded (``max_checks`` model calls; verdicts cached per url+claim).
    """
    if not brief:
        return brief
    marker = "\n## References"
    idx = brief.find(marker)
    body, references = (brief[:idx], brief[idx:]) if idx != -1 else (brief, "")

    sentences = _sentence_spans(body)
    verdict: dict[tuple[str, str], bool] = {}
    checks = [0]

    def sentence_at(pos: int) -> str:
        for start, end in sentences:
            if start <= pos < end:
                return body[start:end]
        return ""

    def supported(span_id: str, pos: int) -> bool:
        span = bank.get(span_id)
        if span is None or not span.url:
            return False
        claim = _CITATION.sub("", sentence_at(pos)).strip()
        if not claim:
            # Can't isolate the claim → don't assess it. KEEP the marker (never delete a
            # citation on a parse miss — that would be silent RACE loss for zero FACT gain).
            return True
        key = (span.url, claim)
        if key in verdict:
            return verdict[key]
        if checks[0] >= max_checks:
            return False  # bound model calls; anything past the cap can't be verified → drop
        page = page_text_fn(span.url)
        if not page.strip():
            verdict[key] = False
            return False
        checks[0] += 1
        try:
            prob = check_fn(page, claim)
        except Exception:  # noqa: BLE001 — a failed check cannot verify → drop the marker
            verdict[key] = False
            return False
        ok = prob >= tau
        verdict[key] = ok
        return ok

    out: list[str] = []
    last = 0
    for m in _CITATION.finditer(body):
        out.append(body[last : m.start()])
        out.append(m.group(0) if supported(m.group(1), m.start()) else "")
        last = m.end()
    out.append(body[last:])
    grounded = re.sub(r"[ \t]{2,}", " ", "".join(out))
    return grounded + references
