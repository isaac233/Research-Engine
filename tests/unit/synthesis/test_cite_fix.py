"""P-Cite post-hoc citation correction (#10) — CiteFix-style, match against the bank."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank, EvidenceSpan
from research_engine.synthesis.cite_fix import fix_citations


def _bank(*spans: tuple[str, str]) -> EvidenceBank:
    return EvidenceBank(
        [EvidenceSpan(id=i, text=t, url=f"https://x/{i}", title=i, verifiable=True) for i, t in spans]
    )


def test_keeps_a_supported_citation() -> None:
    bank = _bank(("e1", "Japan's elderly population will grow sharply through 2050."))
    out = fix_citations("Japan's elderly population grows sharply toward 2050 [e1].", bank)
    assert "[e1]" in out


def test_repoints_a_wrong_citation_to_the_best_span() -> None:
    bank = _bank(
        ("e1", "Global semiconductor supply chains face shortages."),
        ("e2", "Japan's elderly population will grow sharply, reshaping consumer markets by 2050."),
    )
    # Sentence is about Japan aging but wrongly cites the semiconductor span e1.
    out = fix_citations("Japan's elderly population reshapes consumer markets by 2050 [e1].", bank)
    assert "[e2]" in out
    assert "[e1]" not in out


def test_drops_an_unsupported_citation() -> None:
    bank = _bank(("e1", "Global semiconductor supply chains face shortages."))
    out = fix_citations("The Tokyo housing market saw record vacancy rates last year [e1].", bank)
    assert "[e1]" not in out


def test_leaves_uncited_prose_untouched() -> None:
    bank = _bank(("e1", "Japan's elderly population will grow."))
    text = "This report examines several themes.\n\n## Overview\n\nContext follows."
    assert fix_citations(text, bank) == text


def test_preserves_references_section() -> None:
    bank = _bank(("e1", "Japan's elderly population will grow sharply through 2050."))
    brief = "Japan's elderly population grows sharply toward 2050 [e1].\n\n## References\n\n[e1] T — https://x/e1\n"
    out = fix_citations(brief, bank)
    assert "## References" in out
    assert "https://x/e1" in out


def test_keeps_multiple_supported_drops_bogus() -> None:
    bank = _bank(
        ("e1", "Japan's elderly population will grow sharply through 2050."),
        ("e2", "Elderly consumer spending in Japan is rising on healthcare and services."),
        ("e3", "Antarctic ice sheets are melting at an accelerating rate."),
    )
    out = fix_citations(
        "Japan's elderly population grows and elderly consumer spending rises on healthcare [e1][e2][e3].",
        bank,
    )
    assert "[e1]" in out and "[e2]" in out
    assert "[e3]" not in out


def test_empty_brief_and_empty_bank() -> None:
    assert fix_citations("", _bank(("e1", "x"))) == ""
    out = fix_citations("Some text here [e1].", EvidenceBank([]))  # no bank → cite dropped
    assert "[e1]" not in out and "Some text here" in out
