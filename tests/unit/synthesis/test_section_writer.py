"""Unit tests for the section-by-section Writer (Planner/Writer rebuild, Phase 4.1)."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.planning.outline import Outline, OutlineSection
from research_engine.synthesis.section_writer import SectionWriter


def _bank_and_outline():
    src = {
        "title": "Aging",
        "paper": {"url": "https://a.org", "title": "Aging"},
        "meta": {
            "page_text": (
                "Japan's elderly population reaches 35 percent by 2040 clearly. "
                "Senior consumer spending on housing rises sharply each year. "
                "Elderly transportation demand shifts toward accessible services widely."
            )
        },
        "claims": [],
    }
    bank = EvidenceBank.from_pages([src], lambda u: "", query="elderly")
    ids = [s.id for s in bank.spans()]
    outline = Outline(
        sections=(
            OutlineSection("Population", "how many", (ids[0],)),
            OutlineSection("Spending", "consumption", tuple(ids[1:])),
        )
    )
    return bank, outline, ids


class _EchoProvider:
    """Echo the evidence lines from the prompt (they carry the section's [eN])."""

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
        body = messages[-1].content
        lines = [ln for ln in body.splitlines() if ln.strip().startswith("[e")]
        return " ".join(ln.split("] ", 1)[-1] + f" [{ln.split(']')[0].strip('[')}]" for ln in lines)


def test_writes_section_headers_and_references() -> None:
    bank, outline, _ = _bank_and_outline()
    out = SectionWriter(_EchoProvider()).write(outline, bank, "elderly market")
    assert "## Population" in out and "## Spending" in out
    assert "## References" in out and "https://a.org" in out


def test_section_only_cites_its_own_evidence() -> None:
    bank, outline, ids = _bank_and_outline()
    out = SectionWriter(_EchoProvider()).write(outline, bank, "q")
    pop = out.split("## Population")[1].split("## Spending")[0]
    # Population section cites only ids[0], not the Spending ids.
    assert f"[{ids[0]}]" in pop
    for other in ids[1:]:
        assert f"[{other}]" not in pop


def test_section_with_no_resolvable_evidence_skipped() -> None:
    bank, _, ids = _bank_and_outline()
    outline = Outline(sections=(OutlineSection("Ghost", "x", ("e999",)),))
    out = SectionWriter(_EchoProvider()).write(outline, bank, "q")
    assert "## Ghost" not in out


def test_empty_outline_returns_empty() -> None:
    bank, _, _ = _bank_and_outline()
    assert SectionWriter(_EchoProvider()).write(Outline(sections=()), bank, "q") == ""
