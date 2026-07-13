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


def test_numeric_fabrication_dropped() -> None:
    # A cited figure absent from the source is the high-precision fabrication
    # signal — that citation is stripped; the sentence text survives.
    brief = "Japan's elderly share will hit 72% by 2035 [1]."
    sources = [_source("Japan's elderly share reaches 35% by 2040 nationwide.")]
    out = ground_citations(brief, sources)
    assert "[1]" not in out
    assert "72%" in out


def test_nonnumeric_paraphrase_kept() -> None:
    # A reworded, non-numeric claim is kept — word-overlap stripping wrongly
    # removed valid paraphrase citations, so only numeric fabrication is caught.
    brief = "Buffett prizes durable competitive moats and honest managers [1]."
    sources = [_source("The author stresses economic moats and management integrity.")]
    out = ground_citations(brief, sources)
    assert "[1]" in out


def test_numeric_match_supports() -> None:
    brief = "The ratio was 0.8435 in the routing study [1]."
    sources = [_source("Within-routing similarity measured 0.8435 across layers.")]
    out = ground_citations(brief, sources)
    assert "[1]" in out


def test_multi_citation_keeps_supported_drops_other() -> None:
    brief = "Health spending rose 12% as the population aged [1][2]."
    sources = [
        _source("Health spending rose 12% over the decade as ageing accelerated."),
        _source("An unrelated source about 99 gravitational-wave detections."),
    ]
    out = ground_citations(brief, sources)
    assert "[1]" in out  # 12% present in source 1
    assert "[2]" not in out  # 12% absent from source 2


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
    brief = "Metric A was 11% [1]. Metric B was 22% [2]. Metric C was 33% [3]."
    sources = [
        _source("totally unrelated readable text with the figure 90 in it"),
        _source("another unrelated readable passage citing 91 somewhere"),
        _source("yet more unrelated readable content mentioning 92 here"),
    ]
    out = ground_citations(brief, sources)
    assert "[1]" in out and "[2]" in out and "[3]" in out


def test_references_section_untouched() -> None:
    brief = "Body sentence with no citation.\n\n## References\n\n[1] Title — http://x"
    sources = [_source("irrelevant")]
    out = ground_citations(brief, sources)
    assert "## References" in out
    assert "http://x" in out
