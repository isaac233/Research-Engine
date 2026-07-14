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
from typing import Any


@dataclasses.dataclass(frozen=True, slots=True)
class EvidenceSpan:
    """One verbatim span of source text with its citable URL."""

    id: str
    text: str
    url: str
    title: str
    verifiable: bool  # True when url is an HTML page the FACT fetcher can re-read


def _citable_url(source: dict[str, Any]) -> tuple[str, bool]:
    """Best citable URL, preferring an HTML page over a PDF/DOI.

    Returns (url, verifiable). ``verifiable`` is True only when the chosen URL is
    an HTML page (the FACT metric fetches + markdownifies; PDFs/DOIs come back
    unreadable and auto-fail), so a PDF/DOI-only source is cited but flagged.
    """
    paper = source.get("paper") or {}
    candidates = [paper.get("url"), source.get("full_text_url"), paper.get("pdf_url")]
    urls = [str(u) for u in candidates if u]
    for u in urls:
        lu = u.lower()
        if not lu.endswith(".pdf") and "doi.org" not in lu:
            return u, True
    return (urls[0], False) if urls else ("", False)


class EvidenceBank:
    """A collection of verbatim evidence spans addressable by ID."""

    def __init__(self, spans: list[EvidenceSpan]) -> None:
        self._spans = spans
        self._by_id = {s.id: s for s in spans}

    @classmethod
    def from_sources(cls, sources: list[dict[str, Any]]) -> EvidenceBank:
        """Build a bank from serialized ExtractedSource dicts (verbatim evidence)."""
        spans: list[EvidenceSpan] = []
        for source in sources:
            url, verifiable = _citable_url(source)
            title = str(source.get("title") or (source.get("paper") or {}).get("title") or "")
            for claim in source.get("claims", []) or []:
                text = str(claim.get("evidence", "")).strip()
                if not text:
                    continue
                spans.append(
                    EvidenceSpan(
                        id=f"e{len(spans) + 1}",
                        text=text,
                        url=url,
                        title=title,
                        verifiable=verifiable,
                    )
                )
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
