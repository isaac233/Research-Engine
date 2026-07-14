"""Unit tests for the Evidence Memory Bank (Phase 1.0 spike)."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.synthesis.verify_citations import verify_citations


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


def test_page_text_spans_query_ranked() -> None:
    # Verbatim sentences from the enriched page text (paper.abstract) are banked,
    # ranked by query relevance; a source with no structured claims still yields spans.
    page = (
        "Japan's elderly population is growing rapidly toward 2040. "
        "An unrelated aside about local cuisine and festivals. "
        "Consumer spending by seniors reshapes the retail market."
    )
    src = {
        "title": "Aging",
        "paper": {"url": "https://a.org", "title": "Aging", "abstract": page},
        "claims": [],
    }
    bank = EvidenceBank.from_sources([src], query="elderly consumer spending market")
    texts = [s.text for s in bank.spans()]
    assert any("Consumer spending by seniors" in t for t in texts)
    assert all(s.url == "https://a.org" for s in bank.spans())
    # Off-topic cuisine sentence ranked out (only query-relevant kept).
    assert not any("cuisine" in t for t in texts)


def test_empty_bank() -> None:
    bank = EvidenceBank.from_sources([])
    assert bank.spans() == []
    assert bank.references() == ""


# --- Phase 3.2: page-bound evidence extraction -------------------------------


def _pages(mapping):
    """A fetch_fn that returns the markdownified page text for a known URL."""

    def fetch(url: str) -> str:
        return mapping.get(url, "")

    return fetch


def test_from_pages_binds_spans_to_fetched_url() -> None:
    # The span text is extracted FROM the fetched page, so it is a verbatim
    # substring of that page, keyed to the exact URL that was fetched.
    page = (
        "Japan's elderly population is growing rapidly toward 2040. "
        "Consumer spending by seniors reshapes the retail market."
    )
    src = _source([], url="https://a.org/report")
    bank = EvidenceBank.from_pages(
        [src], _pages({"https://a.org/report": page}), query="elderly consumer spending"
    )
    spans = bank.spans()
    assert spans, "page-bound bank should yield spans"
    for s in spans:
        assert s.url == "https://a.org/report"
        assert s.verifiable is True
        assert s.text in page  # verbatim substring of the fetched page


def test_from_pages_verifies_by_construction() -> None:
    # The whole point: a brief citing every page-bound span passes
    # verify-before-cite against the SAME fetch, because each span came from it.
    page = (
        "Health spending rose twelve percent over the decade. "
        "The elderly share reaches thirty-five percent by 2040."
    )
    fetch = _pages({"https://who.int/report": page})
    src = _source([], url="https://who.int/report")
    bank = EvidenceBank.from_pages([src], fetch, query="health spending elderly share")
    brief = " ".join(f"{s.text} [{s.id}]" for s in bank.spans()) + bank.references()
    grounded = verify_citations(brief, bank, fetch)
    # No citation stripped — every span is on its page by construction.
    for s in bank.spans():
        assert f"[{s.id}]" in grounded


def test_from_pages_skips_unfetchable_and_pdf_only() -> None:
    pdf_only = _source([], url=None, pdf_url="https://x.org/a.pdf")
    dead = _source([], url="https://dead.org/gone")  # fetch returns ""
    bank = EvidenceBank.from_pages(
        [pdf_only, dead], _pages({}), query="anything"
    )
    assert bank.spans() == []


def test_from_pages_prefers_stored_page_text_without_fetching() -> None:
    # Extraction already fetched the page; from_pages must mine the stored text
    # (meta.page_text) and NOT re-fetch — re-fetching every URL triggers 429s.
    page = (
        "Japan's elderly population is growing rapidly toward 2040. "
        "Consumer spending by seniors reshapes the retail market."
    )
    src = {
        "title": "Aging",
        "paper": {"url": "https://a.org", "title": "Aging"},
        "meta": {"page_text": page},
        "claims": [],
    }

    def boom(url: str) -> str:
        raise AssertionError("from_pages must not fetch when page_text is stored")

    bank = EvidenceBank.from_pages([src], boom, query="elderly consumer spending")
    spans = bank.spans()
    assert spans
    assert all(s.url == "https://a.org" and s.verifiable and s.text in page for s in spans)


def test_from_pages_caps_fetches() -> None:
    pages = {f"https://s{i}.org": f"Relevant sentence about topic number {i} here." for i in range(20)}
    srcs = [_source([], url=u) for u in pages]
    bank = EvidenceBank.from_pages(srcs, _pages(pages), query="topic", max_fetches=3)
    urls = {s.url for s in bank.spans()}
    assert len(urls) <= 3
