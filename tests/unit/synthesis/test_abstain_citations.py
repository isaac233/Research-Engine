"""W1: attribute-or-abstain citation gate — drop [eN] markers whose sentence is unsupported."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank, EvidenceSpan
from research_engine.synthesis.verify_citations import abstain_citations


def _span(sid: str, text: str = "some span text", url: str = "http://x") -> EvidenceSpan:
    return EvidenceSpan(id=sid, text=text, url=url, title="T", verifiable=True)


def _bank(*spans: EvidenceSpan) -> EvidenceBank:
    return EvidenceBank(list(spans))


def test_marker_dropped_when_unsupported() -> None:
    bank = _bank(_span("e1"))
    brief = "The sky is green [e1]. Water is wet [e1]."
    out = abstain_citations(brief, bank, lambda u: "page", lambda d, c: 0.0)
    assert "[e1]" not in out
    assert "The sky is green" in out and "Water is wet" in out  # prose intact


def test_marker_kept_when_supported() -> None:
    bank = _bank(_span("e1"))
    out = abstain_citations("Fact one [e1].", bank, lambda u: "page", lambda d, c: 1.0)
    assert "[e1]" in out


def test_tau_boundary() -> None:
    bank = _bank(_span("e1"))
    keep = abstain_citations("Claim [e1].", bank, lambda u: "p", lambda d, c: 0.5, tau=0.5)
    drop = abstain_citations("Claim [e1].", bank, lambda u: "p", lambda d, c: 0.49, tau=0.5)
    assert "[e1]" in keep
    assert "[e1]" not in drop


def test_missing_page_text_drops_marker() -> None:
    bank = _bank(_span("e1"))
    out = abstain_citations("Claim [e1].", bank, lambda u: "", lambda d, c: 1.0)
    assert "[e1]" not in out


def test_unknown_span_dropped() -> None:
    bank = _bank(_span("e1"))
    out = abstain_citations("Claim [e9].", bank, lambda u: "p", lambda d, c: 1.0)
    assert "[e9]" not in out


def test_references_section_preserved() -> None:
    bank = _bank(_span("e1"))
    brief = "Body [e1].\n## References\n\n[e1] T — http://x\n"
    out = abstain_citations(brief, bank, lambda u: "", lambda d, c: 0.0)
    assert "## References" in out and "http://x" in out


def test_check_fn_error_is_non_fatal() -> None:
    bank = _bank(_span("e1"))

    def boom(document: str, claim: str) -> float:
        raise RuntimeError("checker down")

    out = abstain_citations("Claim [e1].", bank, lambda u: "p", boom)
    assert "[e1]" not in out and "Claim" in out


def test_max_checks_cap() -> None:
    bank = _bank(_span("e1", url="u1"), _span("e2", url="u2"), _span("e3", url="u3"))
    calls: list[int] = []

    def check(document: str, claim: str) -> float:
        calls.append(1)
        return 1.0

    out = abstain_citations("A [e1]. B [e2]. C [e3].", bank, lambda u: "p", check, max_checks=1)
    assert len(calls) == 1  # bounded model calls
    assert "[e1]" in out  # the one under the cap
    assert "[e2]" not in out and "[e3]" not in out  # over cap → dropped


def test_glued_punctuation_keeps_supported_cite() -> None:
    # Regression (review CRITICAL #1): "claim.[e1]" — period glued to the marker, no space.
    # The old regex splitter mapped the marker to no sentence and force-dropped it even
    # when fully supported. A supported cite MUST survive regardless of punctuation style.
    bank = _bank(_span("e1"), _span("e2"))
    brief = "The fund grew 12% in 2024.[e1] Assets reached $50B.[e2]"
    out = abstain_citations(brief, bank, lambda u: "supporting page", lambda d, c: 1.0)
    assert "[e1]" in out and "[e2]" in out


def test_glued_punctuation_still_drops_unsupported() -> None:
    bank = _bank(_span("e1"))
    brief = "The fund grew 12% in 2024.[e1]"
    out = abstain_citations(brief, bank, lambda u: "unrelated page", lambda d, c: 0.0)
    assert "[e1]" not in out and "The fund grew 12% in 2024." in out


def test_glued_claim_is_isolated_not_the_next_sentence() -> None:
    # The [e1] marker must be checked against ITS claim ("...2024"), not the following
    # sentence. check_fn asserts it receives the correct claim.
    bank = _bank(_span("e1"))
    seen: list[str] = []

    def check(document: str, claim: str) -> float:
        seen.append(claim)
        return 1.0

    abstain_citations("The fund grew in 2024.[e1] Assets fell later.", bank, lambda u: "p", check)
    assert seen and "2024" in seen[0] and "Assets fell" not in seen[0]


def test_empty_brief_returns_empty() -> None:
    assert abstain_citations("", _bank(_span("e1")), lambda u: "p", lambda d, c: 1.0) == ""


def test_repeated_same_claim_checks_once() -> None:
    bank = _bank(_span("e1", url="u1"))
    calls: list[int] = []

    def check(document: str, claim: str) -> float:
        calls.append(1)
        return 1.0

    # same sentence+span twice → one cached verdict, one model call
    out = abstain_citations("Water is wet [e1]. Water is wet [e1].", bank, lambda u: "p", check)
    assert out.count("[e1]") == 2
    assert len(calls) == 1
