"""Structured extraction of methodology, data, results, conflicts, and citations."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from research_engine.browser.policy import URLPolicy
from research_engine.discovery.schema import Paper
from research_engine.extraction.citation import Citation, citations_to_dict, extract_citations
from research_engine.extraction.markdownify import markdownify
from research_engine.extraction.pdf_converter import PDFConverter


@dataclass(frozen=True, slots=True)
class ExtractedClaim:
    """A single claim extracted from a source with evidence."""

    claim: str
    evidence: str
    confidence: str
    source_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExtractedSource:
    """Structured extraction from one source."""

    paper: Paper
    title: str
    summary: str
    methodology: str
    data_summary: str
    results_summary: str
    claims: list[ExtractedClaim]
    citations: list[Citation]
    conflicts: list[dict[str, Any]]
    full_text_url: str | None
    is_oa: bool
    extraction_tool: str
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class StructuredExtractor:
    """Extract structured information from a paper + its resolved full text."""

    def __init__(
        self,
        pdf_converter: PDFConverter | None = None,
        url_policy: URLPolicy | None = None,
    ) -> None:
        self.pdf_converter = pdf_converter or PDFConverter()
        self.url_policy = url_policy or URLPolicy()

    def extract(
        self,
        paper: Paper,
        content: str | None = None,
        content_url: str | None = None,
        is_oa: bool = False,
        project_data: list[dict[str, Any]] | None = None,
        fetch_fn: Callable[[str], bytes] | None = None,
    ) -> ExtractedSource:
        """Extract structured fields from a paper.

        If `content` is not provided, the extractor will attempt to fetch/convert
        from `paper.pdf_url` or `paper.url` when safe.
        """
        project_data = project_data or []
        text = content or ""
        tool = "provided"
        error: str | None = None

        if not text:
            text, tool, error = self._load_content(
                paper, content_url=content_url, is_oa=is_oa, fetch_fn=fetch_fn
            )

        title = paper.title
        summary = self._paragraph(text, 0) or paper.abstract or ""
        methodology = self._section(text, ["method", "methodology", "approach"])
        data_summary = self._section(text, ["data", "dataset", "materials", "corpus"])
        results_summary = self._section(text, ["results", "findings", "evaluation"])

        claims = self._extract_claims(text, paper.source_id)
        citations = extract_citations(text)
        conflicts = self._detect_conflicts(claims, project_data, paper.source_id)

        return ExtractedSource(
            paper=paper,
            title=title,
            summary=summary,
            methodology=methodology,
            data_summary=data_summary,
            results_summary=results_summary,
            claims=claims,
            citations=citations,
            conflicts=conflicts,
            full_text_url=content_url or paper.pdf_url or paper.url,
            is_oa=is_oa,
            extraction_tool=tool,
            error=error,
            meta={"char_count": len(text), "citation_count": len(citations)},
        )

    def _load_content(
        self,
        paper: Paper,
        content_url: str | None = None,
        is_oa: bool = False,
        fetch_fn: Callable[[str], bytes] | None = None,
    ) -> tuple[str, str, str | None]:
        """Load text content for a paper. Returns (text, tool, error)."""
        url = content_url or paper.pdf_url or paper.url
        if url and fetch_fn is not None:
            allowed, reason = self.url_policy.allow(url, resolve_hosts=True)
            if not allowed:
                return (
                    paper.abstract or "",
                    "abstract",
                    f"URL blocked by policy: {reason}",
                )
            if not is_oa:
                return (
                    paper.abstract or "",
                    "abstract",
                    "URL is not open-access; fetch refused",
                )
            try:
                data = fetch_fn(url)
            except Exception as exc:  # noqa: BLE001
                return (
                    paper.abstract or "",
                    "abstract",
                    f"Fetch failed: {exc}",
                )
            is_pdf_url = url.lower().endswith(".pdf") or url == paper.pdf_url
            if is_pdf_url:
                result = self.pdf_converter.convert_bytes(data)
                if result.ok:
                    return (result.markdown, f"pdf:{result.tool}", None)
                return (
                    paper.abstract or "",
                    "abstract",
                    f"PDF conversion failed: {result.error}",
                )
            text = self._decode_text(data)
            md = markdownify(text)
            return (md.markdown, "markdownify", None)

        return (paper.abstract or "", "abstract", None)

    def _decode_text(self, data: bytes) -> str:
        """Decode fetched bytes to text, tolerating binary drift."""
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("latin-1", errors="ignore")

    def _paragraph(self, text: str, index: int) -> str:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if 0 <= index < len(paragraphs):
            return paragraphs[index]
        return ""

    def _section(self, text: str, headers: list[str]) -> str:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            stripped = line.strip()
            if not self._is_heading(stripped):
                continue
            lower = stripped.lower().lstrip("#").strip()
            if any(header in lower for header in headers):
                start = i + 1
                end = start
                while end < len(lines) and not self._is_heading(lines[end]):
                    end += 1
                return "\n".join(lines[start:end]).strip()
        return ""

    def _is_heading(self, line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("#")

    def _extract_claims(self, text: str, source_id: str | None) -> list[ExtractedClaim]:
        """Naive claim extraction: look for sentences with strong result language."""
        claims: list[ExtractedClaim] = []
        markers = ["we find", "we found", "results show", "demonstrates", "indicates", "suggests"]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        for sentence in sentences:
            lower = sentence.lower()
            if any(marker in lower for marker in markers) and len(sentence.split()) >= 5:
                claims.append(
                    ExtractedClaim(
                        claim=sentence.strip(),
                        evidence=sentence.strip(),
                        confidence="low",
                        source_id=source_id,
                    )
                )
        return claims[:10]

    def _detect_conflicts(
        self,
        claims: list[ExtractedClaim],
        project_data: list[dict[str, Any]],
        source_id: str | None,
    ) -> list[dict[str, Any]]:
        """Flag discrepancies with user-provided data. Does not auto-dismiss."""
        conflicts: list[dict[str, Any]] = []
        for fact in project_data:
            fact_text = str(fact.get("text", "")).lower()
            if not fact_text:
                continue
            for claim in claims:
                claim_text = claim.claim.lower()
                if fact_text in claim_text or self._contradiction_word_overlap(fact_text, claim_text):
                    conflicts.append(
                        {
                            "source_id": source_id,
                            "claim": claim.claim,
                            "project_fact": fact,
                            "reason": "overlap with project data detected; review required",
                        }
                    )
                    break
        return conflicts

    def _contradiction_word_overlap(self, a: str, b: str) -> bool:
        """Very naive overlap signal; Phase 5 will replace with LLM-based contradiction detection."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a:
            return False
        overlap = len(words_a & words_b) / len(words_a)
        return overlap > 0.8


def extracted_source_to_dict(source: ExtractedSource) -> dict[str, Any]:
    return {
        "paper": source.paper.to_dict(),
        "title": source.title,
        "summary": source.summary,
        "methodology": source.methodology,
        "data_summary": source.data_summary,
        "results_summary": source.results_summary,
        "claims": [
            {"claim": c.claim, "evidence": c.evidence, "confidence": c.confidence, "source_id": c.source_id}
            for c in source.claims
        ],
        "citations": citations_to_dict(source.citations),
        "conflicts": source.conflicts,
        "full_text_url": source.full_text_url,
        "is_oa": source.is_oa,
        "extraction_tool": source.extraction_tool,
        "error": source.error,
        "meta": source.meta,
    }


def extracted_source_from_dict(data: dict[str, Any]) -> ExtractedSource:
    """Reconstruct an ExtractedSource from its serialized form."""
    return ExtractedSource(
        paper=Paper.from_dict(data["paper"]),
        title=data["title"],
        summary=data["summary"],
        methodology=data["methodology"],
        data_summary=data["data_summary"],
        results_summary=data["results_summary"],
        claims=[
            ExtractedClaim(
                claim=c["claim"],
                evidence=c["evidence"],
                confidence=c["confidence"],
                source_id=c.get("source_id"),
            )
            for c in data.get("claims", [])
        ],
        citations=[Citation(**c) for c in data.get("citations", [])],
        conflicts=data.get("conflicts", []),
        full_text_url=data.get("full_text_url"),
        is_oa=bool(data.get("is_oa", False)),
        extraction_tool=data.get("extraction_tool", "unknown"),
        error=data.get("error"),
        meta=data.get("meta", {}),
    )
