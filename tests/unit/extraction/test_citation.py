"""Unit tests for citation extraction."""

from __future__ import annotations

from research_engine.extraction.citation import extract_citations, normalize_doi


def test_extracts_author_year_citations() -> None:
    text = "Doe (2020) found that performance improved. Smith and Jones (2019) disagreed."
    citations = extract_citations(text)
    assert len(citations) >= 2
    assert any(c.year == 2020 for c in citations)
    assert any(c.year == 2019 for c in citations)


def test_extracts_numbered_citations() -> None:
    text = "This was shown in prior work [1] and confirmed [2]."
    citations = extract_citations(text)
    numbered = [c for c in citations if c.raw.startswith("[")]
    assert len(numbered) == 2


def test_extracts_doi() -> None:
    text = "See 10.1234/example for the dataset."
    citations = extract_citations(text)
    doe_citations = [c for c in citations if c.doi is not None]
    assert any(c.doi == "10.1234/example" for c in doe_citations)


def test_normalize_doi_strips_resolver() -> None:
    assert normalize_doi("https://doi.org/10.1234/example") == "10.1234/example"
    assert normalize_doi("10.1234/example") == "10.1234/example"
