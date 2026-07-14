"""Unit tests for structured extraction."""

from __future__ import annotations

from typing import Any

from research_engine.discovery.schema import Paper
from research_engine.extraction.structured import StructuredExtractor, extracted_source_to_dict


def test_extracts_sections_from_markdown() -> None:
    paper = Paper(
        title="Test Paper",
        source="test",
        source_id="id-1",
        abstract="A short abstract.",
    )
    content = """
# Test Paper

We find that the new method improves accuracy.

## Method

We used a controlled experiment.

## Data

We collected 1,000 samples.

## Results

Accuracy increased by 12%.
"""
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content)

    assert source.title == "Test Paper"
    assert "controlled experiment" in source.methodology
    assert "1,000 samples" in source.data_summary
    assert "12%" in source.results_summary
    assert len(source.claims) >= 1


def test_detects_conflict_with_project_data() -> None:
    paper = Paper(title="Conflict Paper", source="test")
    content = "We find that the accuracy is 95%."
    project_data = [{"text": "The accuracy is 95%"}]
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content, project_data=project_data)
    assert len(source.conflicts) >= 1


def test_extracted_source_to_dict_round_trip_shape() -> None:
    paper = Paper(title="Dict Paper", source="test")
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content="We find a result.")
    data = extracted_source_to_dict(source)
    assert data["title"] == "Dict Paper"
    assert "claims" in data
    assert "citations" in data
    assert "conflicts" in data


def test_no_content_uses_abstract() -> None:
    paper = Paper(title="Abstract Paper", source="test", abstract="This is the abstract.")
    extractor = StructuredExtractor()
    source = extractor.extract(paper)
    assert source.summary == "This is the abstract."
    assert source.extraction_tool == "abstract"


def test_fetch_html_content() -> None:
    paper = Paper(
        title="HTML Paper",
        source="test",
        source_id="html-1",
        url="https://example.com/article",
        abstract="Fallback abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        return b"<html><body><h1>HTML Paper</h1><p>We found a result.</p></body></html>"

    extractor = StructuredExtractor()
    source = extractor.extract(paper, is_oa=True, fetch_fn=fetch_fn)
    assert source.extraction_tool == "markdownify"
    assert "HTML Paper" in source.summary


def test_fetch_pdf_content_with_fake_converter() -> None:
    from research_engine.extraction.pdf_converter import PDFConversionResult, PDFConverter

    paper = Paper(
        title="PDF Paper",
        source="test",
        source_id="pdf-1",
        pdf_url="https://example.com/paper.pdf",
        url="https://example.com/paper",
        abstract="Fallback abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        return b"pdf bytes"

    class FakeConverter(PDFConverter):
        def convert_bytes(self, pdf_bytes: bytes, output_dir: Any = None) -> Any:
            return PDFConversionResult(
                markdown="# PDF Paper\n\nWe found a result.",
                ok=True,
                tool="fake",
            )

    extractor = StructuredExtractor(pdf_converter=FakeConverter())
    source = extractor.extract(paper, is_oa=True, fetch_fn=fetch_fn)
    assert source.extraction_tool == "pdf:fake"
    assert "PDF Paper" in source.summary


def test_fetch_refuses_blocked_url() -> None:
    paper = Paper(
        title="Blocked Paper",
        source="test",
        url="file:///etc/passwd",
        abstract="Safe abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        return b"secret"

    extractor = StructuredExtractor()
    source = extractor.extract(paper, is_oa=True, fetch_fn=fetch_fn)
    assert source.extraction_tool == "abstract"
    assert "blocked" in (source.error or "").lower()


def test_fetch_refuses_non_oa_pdf() -> None:
    # Paywall principle: a non-open-access full-text PDF is still refused.
    paper = Paper(
        title="Non-OA PDF",
        source="test",
        pdf_url="https://example.com/paper.pdf",
        abstract="Fallback abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        return b"paywalled pdf bytes"

    extractor = StructuredExtractor()
    source = extractor.extract(paper, is_oa=False, fetch_fn=fetch_fn)
    assert source.extraction_tool == "abstract"
    assert "refused" in (source.error or "").lower()


def test_fetch_refuses_non_oa_doi() -> None:
    # A non-OA DOI landing (paywalled publisher) is refused.
    paper = Paper(
        title="Non-OA DOI",
        source="test",
        url="https://doi.org/10.1/paywalled",
        abstract="Fallback abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        return b"<html>paywall</html>"

    source = StructuredExtractor().extract(paper, is_oa=False, fetch_fn=fetch_fn)
    assert source.extraction_tool == "abstract"


def test_fetch_allows_non_oa_public_html() -> None:
    # Public HTML landing pages (news/gov/org) are freely readable and are what
    # the FACT metric re-fetches, so extraction reads them even when not flagged
    # open-access. Only non-OA full-text PDFs/DOIs stay refused.
    paper = Paper(
        title="Public Page",
        source="serp",
        url="https://who.int/news-room/fact-sheet",
        abstract="Thin snippet.",
    )

    def fetch_fn(url: str) -> bytes:
        return b"<html><body><h1>Public Page</h1><p>Aging reaches 35% by 2040.</p></body></html>"

    source = StructuredExtractor().extract(paper, is_oa=False, fetch_fn=fetch_fn)
    assert source.extraction_tool == "markdownify"
    assert "35%" in (source.meta.get("page_text") or "")


def test_fetch_falls_back_to_landing_page_when_content_url_is_doi() -> None:
    # Resolver hands a non-OA DOI as content_url; extraction refuses it but reads
    # the HTML landing page (paper.url) instead of collapsing to abstract-only.
    paper = Paper(
        title="Landing",
        source="crossref",
        url="https://example.org/landing",
        abstract="Fallback abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        assert url == "https://example.org/landing"  # DOI refused, landing fetched
        return b"<html><body><p>Full readable landing content here.</p></body></html>"

    source = StructuredExtractor().extract(
        paper, content_url="https://doi.org/10.1/x", is_oa=False, fetch_fn=fetch_fn
    )
    assert source.extraction_tool == "markdownify"
    assert "readable landing" in (source.meta.get("page_text") or "")


def test_fetch_failure_falls_back_to_abstract() -> None:
    paper = Paper(
        title="Fetch Failure Paper",
        source="test",
        url="https://example.com/article",
        abstract="Fallback abstract.",
    )

    def fetch_fn(url: str) -> bytes:
        raise RuntimeError("network down")

    extractor = StructuredExtractor()
    source = extractor.extract(paper, is_oa=True, fetch_fn=fetch_fn)
    assert source.extraction_tool == "abstract"
    assert source.summary == "Fallback abstract."
    assert "fetch failed" in (source.error or "").lower()


def test_prefers_quantitative_claims_when_present() -> None:
    paper = Paper(title="Quantitative Filter", source="test")
    content = (
        "We observe that accuracy improves with larger models. "
        "Latency is reduced by 30% after optimization."
    )
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content)
    assert len(source.claims) == 1
    assert "30%" in source.claims[0].claim
    assert source.claims[0].confidence == "high"


def test_keeps_qualitative_claims_when_no_quantitative_ones() -> None:
    paper = Paper(title="Qualitative Only", source="test")
    content = "Coverage score rewards sources, claims, and citations."
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content)
    assert len(source.claims) == 1
    assert source.claims[0].confidence == "medium"


def test_merges_adjacent_continuation_claims() -> None:
    paper = Paper(title="Merged Claim", source="test")
    content = (
        "The new optimizer reduces memory usage. "
        "It also improves throughput by 25%."
    )
    extractor = StructuredExtractor()
    source = extractor.extract(paper, content=content)
    assert len(source.claims) == 1
    assert "memory usage" in source.claims[0].claim
    assert "25%" in source.claims[0].claim
