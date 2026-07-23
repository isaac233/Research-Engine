"""Unit tests for verify-before-cite (Phase 1.0 corrected)."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.synthesis.verify_citations import verify_citations


def _bank(url, evidence):
    src = {"title": "T", "paper": {"url": url, "title": "T"}, "claims": [{"claim": "c", "evidence": evidence}]}
    return EvidenceBank.from_sources([src])


def test_citation_kept_when_span_on_page() -> None:
    bank = _bank("https://a.org", "Japan's elderly share reaches 35% by 2040.")
    brief = "Japan's elderly share reaches 35% by 2040 [e1]."
    page = {"https://a.org": "... report ... Japan's elderly share reaches 35% by 2040 nationwide ..."}
    out = verify_citations(brief, bank, lambda u: page.get(u, ""))
    assert "[e1]" in out


def test_citation_stripped_when_span_absent() -> None:
    bank = _bank("https://paywall.org", "Japan's elderly share reaches 35% by 2040.")
    brief = "Japan's elderly share reaches 35% by 2040 [e1]."
    # Paywalled stub page does not contain the span.
    out = verify_citations(brief, bank, lambda u: "Sign in to view this article.")
    assert "[e1]" not in out


def test_fetch_failure_strips_citation() -> None:
    bank = _bank("https://x.org", "Some verbatim span text about aging.")
    brief = "Some verbatim span text about aging [e1]."

    def boom(_u):
        raise RuntimeError("down")

    out = verify_citations(brief, bank, boom)
    assert "[e1]" not in out


def test_references_preserved() -> None:
    bank = _bank("https://a.org", "Verbatim span present here on page.")
    brief = "Verbatim span present here on page [e1]." + bank.references()
    out = verify_citations(brief, bank, lambda u: "text Verbatim span present here on page text")
    assert "## References" in out


def test_page_fetched_once_per_url() -> None:
    src = {
        "title": "T",
        "paper": {"url": "https://a.org", "title": "T"},
        "claims": [
            {"claim": "1", "evidence": "First verbatim span here."},
            {"claim": "2", "evidence": "Second verbatim span here."},
        ],
    }
    bank = EvidenceBank.from_sources([src])
    brief = "First verbatim span here [e1]. Second verbatim span here [e2]."
    calls: list[str] = []

    def fetch(u):
        calls.append(u)
        return "First verbatim span here. Second verbatim span here."

    verify_citations(brief, bank, fetch)
    assert calls == ["https://a.org"]  # cached across both spans
