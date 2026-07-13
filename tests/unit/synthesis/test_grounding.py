"""Unit tests for post-synthesis citation grounding."""

from __future__ import annotations

from research_engine.synthesis.grounding import ground_citations


def _source(text: str, title: str = "S") -> dict:
    return {"title": title, "results_summary": text, "claims": []}


def test_supported_citation_kept() -> None:
    brief = "Japan's population aged 65+ will reach 35% by 2040 [1]."
    sources = [_source("Results: the share aged 65+ reaches 35% by 2040 nationwide.")]
    out = ground_citations(brief, sources)
    assert "[1]" in out


def test_unsupported_citation_dropped() -> None:
    brief = "Quantum tunneling accelerates semiconductor decay [1]."
    sources = [_source("The elderly share of Japan rises steadily through 2050.")]
    out = ground_citations(brief, sources)
    assert "[1]" not in out
    # The sentence text itself survives; only the citation marker is stripped.
    assert "Quantum tunneling" in out


def test_numeric_match_supports() -> None:
    brief = "The ratio was 0.8435 in the routing study [1]."
    sources = [_source("Within-routing similarity measured 0.8435 across layers.")]
    out = ground_citations(brief, sources)
    assert "[1]" in out


def test_multi_citation_keeps_supported_drops_other() -> None:
    brief = "Aging raises health spending [1][2]."
    sources = [
        _source("Health spending rises sharply as the population ages."),
        _source("Unrelated: gravitational waves from black-hole mergers."),
    ]
    out = ground_citations(brief, sources)
    assert "[1]" in out
    assert "[2]" not in out


def test_out_of_range_citation_dropped_no_crash() -> None:
    brief = "A claim with a dangling citation [9]."
    sources = [_source("some text")]
    out = ground_citations(brief, sources)
    assert "[9]" not in out


def test_empty_source_keeps_citation() -> None:
    # A source that did not re-fetch (empty text) cannot disprove the claim, so
    # the citation is kept rather than hidden.
    brief = "Some specific factual claim about aging economics [1]."
    sources = [_source("")]
    out = ground_citations(brief, sources)
    assert "[1]" in out


def test_floor_keeps_all_when_every_citation_unsupported() -> None:
    # >=3 citations all failing means a systemic re-fetch failure, not a wholly
    # fabricated brief; keep the original rather than ship a citation-less brief.
    brief = "Alpha claim [1]. Beta claim [2]. Gamma claim [3]."
    sources = [
        _source("totally unrelated readable text one two three four five"),
        _source("another unrelated readable passage six seven eight nine"),
        _source("yet more unrelated readable content ten eleven twelve"),
    ]
    out = ground_citations(brief, sources)
    assert "[1]" in out and "[2]" in out and "[3]" in out


def test_references_section_untouched() -> None:
    brief = "Body sentence with no citation.\n\n## References\n\n[1] Title — http://x"
    sources = [_source("irrelevant")]
    out = ground_citations(brief, sources)
    assert "## References" in out
    assert "http://x" in out
