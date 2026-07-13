"""Unit tests for pre-screening snippet enrichment."""

from __future__ import annotations

from research_engine.discovery.schema import Paper
from research_engine.screening.enricher import enrich_snippets

_PAGE_HTML = (
    "<html><body><h1>Japan ageing report</h1>"
    + "<p>" + "Japan's population aged 65+ will reach 35% by 2040. " * 30 + "</p>"
    + "</body></html>"
)


def _thin_web_paper(url: str = "https://example.org/report") -> Paper:
    return Paper(
        title="Japan ageing",
        url=url,
        abstract="Short 150-char snippet.",
        source="serp",
        source_id=url,
    )


def test_enrich_replaces_thin_snippet_with_page_text() -> None:
    def fetch(url: str) -> bytes:
        return _PAGE_HTML.encode("utf-8")

    enriched = enrich_snippets([_thin_web_paper()], fetch_fn=fetch)
    assert len(enriched) == 1
    assert "population aged 65+" in enriched[0].abstract
    assert len(enriched[0].abstract) > 300
    assert enriched[0].meta["enriched_from_page"] is True
    assert enriched[0].meta["snippet"] == "Short 150-char snippet."


def test_fetch_failure_keeps_original_paper() -> None:
    def fetch(url: str) -> bytes:
        raise RuntimeError("network down")

    papers = [_thin_web_paper()]
    enriched = enrich_snippets(papers, fetch_fn=fetch)
    assert enriched[0].abstract == "Short 150-char snippet."
    assert "enriched_from_page" not in enriched[0].meta


def test_non_web_source_untouched() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return _PAGE_HTML.encode("utf-8")

    paper = Paper(
        title="Crossref stub",
        url="https://doi.org/10.1/x",
        abstract="tiny",
        source="crossref",
    )
    enriched = enrich_snippets([paper], fetch_fn=fetch)
    assert calls == []
    assert enriched[0].abstract == "tiny"


def test_thick_abstract_untouched() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return b""

    paper = Paper(
        title="Already readable",
        url="https://example.org/page",
        abstract="A" * 400,
        source="serp",
    )
    enrich_snippets([paper], fetch_fn=fetch)
    assert calls == []


def test_policy_blocked_url_untouched() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return _PAGE_HTML.encode("utf-8")

    paper = _thin_web_paper(url="http://169.254.169.254/latest/meta-data")
    enriched = enrich_snippets([paper], fetch_fn=fetch)
    assert calls == []
    assert enriched[0].abstract == "Short 150-char snippet."


def test_max_fetches_cap_respected() -> None:
    calls: list[str] = []

    def fetch(url: str) -> bytes:
        calls.append(url)
        return _PAGE_HTML.encode("utf-8")

    papers = [_thin_web_paper(url=f"https://example.org/p{i}") for i in range(5)]
    enriched = enrich_snippets(papers, fetch_fn=fetch, max_fetches=2)
    assert len(calls) == 2
    assert sum(1 for p in enriched if p.meta.get("enriched_from_page")) == 2
    # Uncapped papers still present, unchanged.
    assert len(enriched) == 5


def test_excerpt_is_capped() -> None:
    def fetch(url: str) -> bytes:
        return ("<p>" + "word " * 5000 + "</p>").encode("utf-8")

    enriched = enrich_snippets([_thin_web_paper()], fetch_fn=fetch, excerpt_chars=1000)
    assert len(enriched[0].abstract) <= 1000
