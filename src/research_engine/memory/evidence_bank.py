"""Evidence Memory Bank (Phase 1.0 spike).

Holds verbatim evidence spans keyed by a short ID and a citable URL, built from
the engine's already-extracted ``ExtractedSource.claims[].evidence`` (which the
extraction substring guard has already verified is verbatim from the source).
The attribute-first writer generates each sentence FROM these spans and cites the
span's ID, so the delivered citation is grounded by construction — and the URL is
the HTML page the FACT verifier can re-read, not a PDF/DOI it cannot.
"""

from __future__ import annotations

import dataclasses
import os
import re
from collections.abc import Callable
from typing import Any

# Split page text into sentence spans (keep the terminator; ignore decimals like
# "3.5%" by requiring whitespace/end after the .!? ).
_SENTENCE = re.compile(r"[^.!?\n]*(?:[.!?](?=\s|$)|\n|$)")
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "the a an of to in for and or but with on at by is are was were be as that this "
    "these those it its from into than then so such not no can will may would could "
    "which who what when where how".split()
)
# Verbatim page sentences to bank per source (query-ranked). Page-bound spans are
# all verified-by-construction, so more of them = more comprehensive brief at no
# FACT cost; the writer is the only thing that caps length.
_MAX_PAGE_SPANS = 20


def _sentences(text: str) -> list[str]:
    if not text.strip():
        return []
    return [s.strip() for s in _SENTENCE.findall(text) if 25 <= len(s.strip()) <= 400]


def _terms(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP and len(t) > 2}


def _query_ranked(sentences: list[str], query_terms: set[str], limit: int) -> list[str]:
    """Top verbatim sentences by query-term overlap (relevance), original order kept."""
    if not query_terms:
        return sentences[:limit]
    scored = [(len(_terms(s) & query_terms), i, s) for i, s in enumerate(sentences)]
    top = sorted((t for t in scored if t[0] > 0), key=lambda t: (-t[0], t[1]))[:limit]
    return [s for _, _, s in sorted(top, key=lambda t: t[1])]


@dataclasses.dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """One verbatim span of source text with its citable URL."""

    id: str
    text: str
    url: str
    title: str
    verifiable: bool  # True when url is an HTML page the FACT fetcher can re-read


def _pdf_citable() -> bool:
    """PDF URLs are citable when W5 PDF ingest is on.

    The official FACT pipeline fetches via Jina Reader, which reads PDFs — and
    our parity fetcher (bench/fact.py default_fetcher) converts PDFs too. So a
    PDF citation is verifiable whenever the engine can also read PDFs (same W5
    flag). Off ⇒ byte-identical legacy behavior (PDF-only sources skipped).
    """
    return bool(os.environ.get("RESEARCH_ENGINE_PDF_INGEST"))


def _citable_url(source: dict[str, Any]) -> tuple[str, bool]:
    """Best citable URL, preferring an HTML page over a PDF/DOI.

    Returns (url, verifiable). ``verifiable`` is True when the chosen URL is an
    HTML page — or a PDF while W5 ingest is on (the FACT fetcher then converts
    it). Bare DOIs stay unverifiable; a flagged source is cited but skipped by
    ``from_pages``.
    """
    paper = source.get("paper") or {}
    candidates = [paper.get("url"), source.get("full_text_url"), paper.get("pdf_url")]
    urls = [str(u) for u in candidates if u]
    for u in urls:
        lu = u.lower()
        if not lu.endswith(".pdf") and "doi.org" not in lu:
            return u, True
    if _pdf_citable():
        for u in urls:
            lu = u.lower()
            if lu.endswith(".pdf") and "doi.org" not in lu:
                return u, True
    return (urls[0], False) if urls else ("", False)


class EvidenceBank:
    """A collection of verbatim evidence spans addressable by ID."""

    def __init__(self, spans: list[EvidenceSpan]) -> None:
        self._spans = spans
        self._by_id = {s.id: s for s in spans}

    @classmethod
    def from_sources(cls, sources: list[dict[str, Any]], query: str = "") -> EvidenceBank:
        """Build a bank of VERBATIM evidence spans from serialized ExtractedSource dicts.

        Two verbatim sources, both re-verifiable by the FACT metric:
        1. ``claims[].evidence`` — substring-guarded quotes from the source text.
        2. Query-ranked sentences from the page text the enricher stored in
           ``paper.abstract`` (the same markdownify the FACT fetcher re-reads), so
           every readable web source contributes spans even without structured
           claims. Summary/paraphrase fields are NOT mined — a spike measured them
           at ~8% citation accuracy (paraphrases don't re-verify) vs ~67% for
           verbatim spans. Claim spans are added first; duplicates dropped.
        """
        spans: list[EvidenceSpan] = []
        seen: set[str] = set()
        query_terms = _terms(query)

        def add(text: str, url: str, title: str, verifiable: bool) -> None:
            key = " ".join(text.lower().split())
            if not key or key in seen:
                return
            seen.add(key)
            spans.append(
                EvidenceSpan(id=f"e{len(spans) + 1}", text=text, url=url, title=title, verifiable=verifiable)
            )

        for source in sources:
            url, verifiable = _citable_url(source)
            title = str(source.get("title") or (source.get("paper") or {}).get("title") or "")
            for claim in source.get("claims", []) or []:
                add(str(claim.get("evidence", "")).strip(), url, title, verifiable)
            page_text = str((source.get("paper") or {}).get("abstract", ""))
            for sentence in _query_ranked(_sentences(page_text), query_terms, _MAX_PAGE_SPANS):
                add(sentence, url, title, verifiable)
        return cls(spans)

    @classmethod
    def from_pages(
        cls,
        sources: list[dict[str, Any]],
        fetch_fn: Callable[[str], str],
        query: str = "",
        *,
        max_fetches: int = 8,
    ) -> EvidenceBank:
        """Build a PAGE-BOUND bank: fetch each source's citable URL, extract
        verbatim spans FROM that fetch, and key every span to that exact URL.

        This is the fix for the disconnect that sank the spike: ``from_sources``
        mines ``paper.abstract``, which for academic sources is NOT the live
        content at ``paper.url`` that the FACT metric re-fetches — so those spans
        never re-verify. Here the span text is a verbatim substring of the very
        page a citation points to (``fetch_fn`` is the same markdownify transform
        FACT performs), so verify-before-cite passes by construction. PDF/DOI-only
        sources are skipped (the fetcher cannot read them); fetch failures are
        non-fatal; fetches are capped.
        """
        spans: list[EvidenceSpan] = []
        seen: set[str] = set()
        query_terms = _terms(query)
        fetched = 0

        def add(text: str, url: str, title: str) -> None:
            key = " ".join(text.lower().split())
            if not key or key in seen:
                return
            seen.add(key)
            spans.append(
                EvidenceSpan(id=f"e{len(spans) + 1}", text=text, url=url, title=title, verifiable=True)
            )

        for source in sources:
            url, verifiable = _citable_url(source)
            if not url or not verifiable:  # PDF/DOI-only can't be re-fetched → skip
                continue
            # Extraction already fetched this page and stored the text; reuse it so
            # we don't re-fetch every URL (which rate-limits real sites). Only fall
            # back to a live fetch when no stored text is available.
            page_text = str((source.get("meta") or {}).get("page_text") or "")
            if not page_text.strip():
                if url.split("?", 1)[0].split("#", 1)[0].lower().endswith(".pdf"):
                    # A W5-citable PDF is only usable via its stored CONVERTED text
                    # (react read_fn ran PDFConverter); fetch_fn here is the plain
                    # HTML transform and would mine spans from raw PDF bytes.
                    continue
                if fetched >= max_fetches:
                    continue
                try:
                    page_text = fetch_fn(url)
                except Exception:  # noqa: BLE001 — a failed fetch contributes nothing, not fatal
                    continue
                if not page_text.strip():
                    continue
                fetched += 1
            title = str(source.get("title") or (source.get("paper") or {}).get("title") or "")
            for sentence in _query_ranked(_sentences(page_text), query_terms, _MAX_PAGE_SPANS):
                add(sentence, url, title)
        return cls(spans)

    def spans(self) -> list[EvidenceSpan]:
        return list(self._spans)

    def get(self, span_id: str) -> EvidenceSpan | None:
        return self._by_id.get(span_id)

    def references(self) -> str:
        """Deterministic References section mapping each cited [id] to its URL."""
        if not self._spans:
            return ""
        # One reference line per distinct URL, listing the span IDs it backs.
        seen: dict[str, list[str]] = {}
        titles: dict[str, str] = {}
        for s in self._spans:
            key = s.url or s.title
            seen.setdefault(key, []).append(s.id)
            titles[key] = s.title or key
        lines = [
            f"[{', '.join(ids)}] {titles[key]} — {key}" if key else f"[{', '.join(ids)}] {titles[key]}"
            for key, ids in seen.items()
        ]
        return "\n\n## References\n\n" + "\n".join(lines) + "\n"
