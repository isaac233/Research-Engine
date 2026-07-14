"""Structured extraction of methodology, data, results, conflicts, and citations."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from research_engine.browser.policy import URLPolicy
from research_engine.discovery.schema import Paper
from research_engine.extraction.citation import Citation, citations_to_dict, extract_citations
from research_engine.extraction.llm_extractor import LLMSectionExtractor
from research_engine.extraction.markdownify import markdownify
from research_engine.extraction.pdf_converter import PDFConverter

# Cap on the fetched page text kept for page-bound evidence mining (enough spans
# for coverage without bloating campaign meta).
_PAGE_TEXT_CAP = 8000


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
    conclusions: str = ""
    replication_notes: str = ""
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class StructuredExtractor:
    """Extract structured information from a paper + its resolved full text."""

    def __init__(
        self,
        pdf_converter: PDFConverter | None = None,
        url_policy: URLPolicy | None = None,
        llm_extractor: LLMSectionExtractor | None = None,
    ) -> None:
        self.pdf_converter = pdf_converter or PDFConverter()
        self.url_policy = url_policy or URLPolicy()
        self.llm_extractor = llm_extractor

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
        citations = extract_citations(text)
        meta: dict[str, Any] = {"char_count": len(text), "citation_count": len(citations)}

        # Only abstract text is available: do not fabricate a methods/data section.
        abstract_only = tool == "abstract"
        if abstract_only:
            meta["degraded"] = "abstract_only"
        else:
            # Keep the fetched page text (bound to this source's URL) so downstream
            # page-bound evidence can mine verbatim spans without re-fetching.
            meta["page_text"] = text[:_PAGE_TEXT_CAP]

        conclusions = ""
        replication_notes = ""
        used_llm = False
        if self.llm_extractor is not None and text and not abstract_only:
            llm = self.llm_extractor.extract_sections(title, paper.abstract or "", text)
            if llm.methodology or llm.results_summary or llm.claims:
                used_llm = True
                methodology = llm.methodology
                data_summary = llm.data_summary
                results_summary = llm.results_summary
                conclusions = llm.conclusions
                replication_notes = llm.replication_notes
                claims = [
                    ExtractedClaim(
                        claim=c.claim,
                        evidence=c.evidence,
                        confidence=c.confidence,
                        source_id=paper.source_id,
                    )
                    for c in llm.claims
                ]
                tool = f"llm:{self.llm_extractor.model or 'default'}"
                meta["llm"] = llm.meta

        if not used_llm:
            # Regex fallback (LLM unavailable, failed, or abstract-only).
            methodology = self._section(text, ["method", "methodology", "approach"])
            data_summary = self._section(text, ["data", "dataset", "materials", "corpus"])
            results_summary = self._section(text, ["results", "findings", "evaluation"])
            claims = self._extract_claims(text, paper.source_id)

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
            conclusions=conclusions,
            replication_notes=replication_notes,
            error=error,
            meta=meta,
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
        markers = [
            "we find",
            "we found",
            "results show",
            "demonstrates",
            "indicated",
            "indicates",
            "suggests",
            "improved",
            "improves",
            "reduced",
            "reduces",
            "increased",
            "increases",
            "decreased",
            "decreases",
            "rewards",
            "penalizes",
            "optimized",
            "optimizes",
            "enhanced",
            "enhances",
            "enables",
            "supports",
            "exceeds",
            "exceeded",
            "surpasses",
            "surpassed",
            "outperforms",
            "outperformed",
            "beats",
            "achieves",
            "achieved",
            "yields",
            "yielded",
            "produces",
            "produced",
            "must",
            "should",
            "will",
            "required",
            "requirement",
            "limitation",
            "constraint",
            "bottleneck",
            "risk",
            "decision",
            "decided",
            "chosen",
            "trade-off",
            "tradeoff",
            "recommend",
            "recommended",
            "pattern",
            "anti-pattern",
        ]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        raw_claims: list[ExtractedClaim] = []
        for sentence in sentences:
            lower = sentence.lower()
            if any(marker in lower for marker in markers) and len(sentence.split()) >= 5:
                raw_claims.append(
                    ExtractedClaim(
                        claim=sentence.strip(),
                        evidence=sentence.strip(),
                        confidence=self._claim_confidence(sentence),
                        source_id=source_id,
                    )
                )
        merged = self._merge_adjacent_claims(raw_claims)
        return self._filter_claims_by_confidence(merged)[:10]

    _CONTINUATION_PREFIXES: tuple[str, ...] = (
        "it ",
        "this ",
        "that ",
        "also ",
        "furthermore ",
        "moreover ",
        "additionally ",
        "in addition ",
        "consequently ",
        "therefore ",
        "thus ",
        "as a result ",
    )

    def _merge_adjacent_claims(self, claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
        """Merge consecutive claim sentences that continue the same finding."""
        if not claims:
            return claims
        merged: list[ExtractedClaim] = []
        for claim in claims:
            if merged and claim.claim.lower().startswith(self._CONTINUATION_PREFIXES):
                prev = merged[-1]
                merged[-1] = ExtractedClaim(
                    claim=f"{prev.claim} {claim.claim}",
                    evidence=f"{prev.evidence} {claim.evidence}",
                    confidence="high" if prev.confidence == "high" or claim.confidence == "high" else prev.confidence,
                    source_id=prev.source_id,
                )
            else:
                merged.append(claim)
        return merged

    def _claim_confidence(self, sentence: str) -> str:
        """Prefer quantitative claims; mark others as medium/low."""
        has_number = bool(re.search(r"\d", sentence)) or "%" in sentence
        if has_number:
            return "high"
        return "medium"

    def _filter_claims_by_confidence(self, claims: list[ExtractedClaim]) -> list[ExtractedClaim]:
        """When quantitative claims exist, drop weaker heuristic claims.

        This raises precision by focusing on concrete, measurable findings when
        they are present, without discarding all qualitative claims in a source.
        """
        if not claims:
            return claims
        if any(c.confidence == "high" for c in claims):
            return [c for c in claims if c.confidence == "high"]
        return claims

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
        "conclusions": source.conclusions,
        "replication_notes": source.replication_notes,
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
        conclusions=data.get("conclusions", ""),
        replication_notes=data.get("replication_notes", ""),
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
