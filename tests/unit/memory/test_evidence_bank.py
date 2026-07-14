"""Unit tests for the Evidence Memory Bank (Phase 1.0 spike)."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank


def _source(claims, url="https://example.org/page", pdf_url=None, full_text_url=None, title="T"):
    return {
        "title": title,
        "paper": {"url": url, "pdf_url": pdf_url, "title": title},
        "full_text_url": full_text_url,
        "claims": claims,
    }


def test_build_from_spans_sequential_ids() -> None:
    src = _source(
        [
            {"claim": "aging rises", "evidence": "The elderly share reaches 35% by 2040."},
            {"claim": "spending up", "evidence": "Health spending rose 12% over the decade."},
        ]
    )
    bank = EvidenceBank.from_sources([src])
    spans = bank.spans()
    assert [s.id for s in spans] == ["e1", "e2"]
    assert spans[0].text == "The elderly share reaches 35% by 2040."
    assert bank.get("e2").text == "Health spending rose 12% over the decade."
    assert bank.get("missing") is None


def test_empty_evidence_skipped() -> None:
    src = _source(
        [
            {"claim": "a", "evidence": ""},
            {"claim": "b", "evidence": "Real verbatim span here."},
        ]
    )
    bank = EvidenceBank.from_sources([src])
    assert [s.id for s in bank.spans()] == ["e1"]
    assert bank.get("e1").text == "Real verbatim span here."


def test_html_url_preferred_over_pdf() -> None:
    src = _source(
        [{"claim": "x", "evidence": "span"}],
        url="https://who.int/report",
        pdf_url="https://who.int/report.pdf",
    )
    span = EvidenceBank.from_sources([src]).get("e1")
    assert span.url == "https://who.int/report"
    assert span.verifiable is True


def test_pdf_or_doi_only_flagged_unverifiable() -> None:
    pdf = _source([{"claim": "x", "evidence": "span"}], url=None, pdf_url="https://x.org/a.pdf")
    doi = _source([{"claim": "y", "evidence": "span2"}], url="https://doi.org/10.1/x")
    pdf_span = EvidenceBank.from_sources([pdf]).get("e1")
    doi_span = EvidenceBank.from_sources([doi]).get("e1")
    assert pdf_span.url == "https://x.org/a.pdf"
    assert pdf_span.verifiable is False
    assert doi_span.verifiable is False


def test_references_render() -> None:
    src = _source([{"claim": "x", "evidence": "span"}], url="https://a.org", title="Alpha")
    refs = EvidenceBank.from_sources([src]).references()
    assert "[e1]" in refs and "Alpha" in refs and "https://a.org" in refs


def test_empty_bank() -> None:
    bank = EvidenceBank.from_sources([])
    assert bank.spans() == []
    assert bank.references() == ""
