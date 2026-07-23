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


class _CaptureProvider:
    def __init__(self) -> None:
        self.seen = ""

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
        self.seen += messages[-1].content
        return "Elderly population rises [e1]."


def test_max_sentences_cap_scales_the_requested_sentence_count() -> None:
    # RACE is reference-normalized against a ~63k reference; our ~13k brief is 1/5 scale.
    # A higher max_sentences must let a well-supported section request more sentences.
    text = " ".join(f"Fact number {i} about elderly consumption is notable clearly." for i in range(6))
    src = {"title": "T", "paper": {"url": "https://a.org", "title": "T"}, "meta": {"page_text": text}, "claims": []}
    bank = EvidenceBank.from_pages([src], lambda u: "", query="elderly")
    ids = [s.id for s in bank.spans()]
    outline = Outline(sections=(OutlineSection("S", "all", tuple(ids)),))

    small, big = _CaptureProvider(), _CaptureProvider()
    SectionWriter(small, synthesis=True, max_sentences=3).write(outline, bank, "q")
    SectionWriter(big, synthesis=True, max_sentences=8).write(outline, bank, "q")

    def _aim(prompt: str) -> int:
        after = prompt.split("Aim for ", 1)[1]
        return int(after.split(" to ", 1)[0])

    assert len(ids) >= 5  # enough spans for the cap to bite
    assert _aim(big.seen) > _aim(small.seen)


def test_synthesis_mode_asks_for_analytical_paragraphs_and_bans_lists() -> None:
    bank, outline, _ = _bank_and_outline()
    prov = _CaptureProvider()
    SectionWriter(prov, synthesis=True).write(outline, bank, "elderly")
    seen = prov.seen.lower()
    assert "analytical" in seen or "cohesive" in seen
    assert "bullet" in seen  # lists banned as the body


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


def test_paragraph_cite_mode_keeps_headers_and_own_evidence() -> None:
    # Paragraph-granularity (arXiv:2604.01432): coherent prose citing the span
    # SET, not one span per sentence. Same structural invariants must hold.
    bank, outline, ids = _bank_and_outline()
    out = SectionWriter(_EchoProvider(), paragraph_cite=True).write(outline, bank, "q")
    assert "## Population" in out and "## Spending" in out and "## References" in out
    pop = out.split("## Population")[1].split("## Spending")[0]
    assert f"[{ids[0]}]" in pop
    for other in ids[1:]:
        assert f"[{other}]" not in pop


def test_paragraph_cite_uses_grouped_template() -> None:
    # The paragraph template must ask for grouped end-of-paragraph citations,
    # not a per-sentence citation, and must not force a sentence count.
    captured: dict[str, str] = {}

    class _Capture:
        def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
            captured["user"] = messages[-1].content
            return "Synthesised prose. [e0]"

    bank, outline, _ = _bank_and_outline()
    SectionWriter(_Capture(), paragraph_cite=True).write(outline, bank, "q")
    assert "paragraph" in captured["user"].lower()
    assert "sentence must restate one" not in captured["user"]


def test_guidance_appended_to_section_prompts_and_title_overridden() -> None:
    # P1 rubric scaffold: guidance rides every section prompt; report_title replaces
    # the "Research Brief: <prompt>" header. Both empty = legacy (other tests).
    bank, outline, _ = _bank_and_outline()
    provider = _CaptureProvider()
    writer = SectionWriter(
        provider,
        "m",
        guidance="Quality criteria:\n- Define the cohort explicitly",
        report_title="Sovereign Wealth Investment Strategies",
    )
    out = writer.write(outline, bank, "how governments invest")
    assert "Define the cohort explicitly" in provider.seen
    assert out.startswith("# Sovereign Wealth Investment Strategies\n")
    assert "Research Brief:" not in out


def test_no_guidance_keeps_legacy_header() -> None:
    bank, outline, _ = _bank_and_outline()
    writer = SectionWriter(_CaptureProvider(), "m")
    out = writer.write(outline, bank, "how governments invest")
    assert out.startswith("# Research Brief: how governments invest")
