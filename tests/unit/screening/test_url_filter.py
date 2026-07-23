"""Unit tests for the fetchable-URL filter (evidence-volume amplifier)."""

from __future__ import annotations

from research_engine.screening.url_filter import fetchability_score, prefer_fetchable


def test_public_html_outranks_pdf_and_doi() -> None:
    assert fetchability_score("https://who.int/report") > fetchability_score(
        "https://who.int/report.pdf"
    )
    assert fetchability_score("https://who.int/report") > fetchability_score(
        "https://doi.org/10.1/abc"
    )


def test_known_paywall_hosts_deprioritised() -> None:
    assert fetchability_score("https://www.researchgate.net/publication/1") < fetchability_score(
        "https://nippon.com/en/article"
    )
    assert fetchability_score("https://www.sciencedirect.com/x") < fetchability_score(
        "https://example.org/x"
    )


def test_none_url_scores_lowest() -> None:
    assert fetchability_score(None) == 0


def test_prefer_fetchable_reorders_but_keeps_all_stably() -> None:
    # (id, url) tuples; fetchable public pages float up, order otherwise preserved.
    items = [
        ("a", "https://doi.org/10.1/x"),
        ("b", "https://who.int/aging"),
        ("c", "https://researchgate.net/p/2"),
        ("d", "https://nippon.com/en/y"),
    ]
    ranked = prefer_fetchable(items, url_of=lambda t: t[1])
    ids = [t[0] for t in ranked]
    assert ids == ["b", "d", "a", "c"]  # public HTML first; DOI before researchgate
    assert set(ids) == {"a", "b", "c", "d"}  # nothing dropped


def test_prefer_fetchable_empty() -> None:
    assert prefer_fetchable([], url_of=lambda t: t) == []
