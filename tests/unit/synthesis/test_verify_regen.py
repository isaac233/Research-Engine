"""Verify-and-regenerate citation grounding (#13) — model-entailment vs the bank span."""

from __future__ import annotations

from research_engine.llm.provider import Message
from research_engine.memory.evidence_bank import EvidenceBank, EvidenceSpan
from research_engine.synthesis.verify_regen import verify_regen


def _bank(*spans: tuple[str, str]) -> EvidenceBank:
    return EvidenceBank(
        [EvidenceSpan(id=i, text=t, url=f"https://x/{i}", title=i, verifiable=True) for i, t in spans]
    )


# --- verify mode (entails injected → deterministic, no provider) ------------------


def test_keeps_entailed_citation() -> None:
    bank = _bank(("e1", "Japan's elderly population will grow sharply through 2050."))
    out = verify_regen(
        "Japan's elderly population grows sharply toward 2050 [e1].",
        bank, provider=None, entails=lambda c, s: True,  # type: ignore[arg-type]
    )
    assert "[e1]" in out


def test_drops_unentailed_citation() -> None:
    bank = _bank(("e1", "Global semiconductor supply chains face shortages."))
    out = verify_regen(
        "The Tokyo housing market saw record vacancy rates [e1].",
        bank, provider=None, entails=lambda c, s: False,  # type: ignore[arg-type]
    )
    assert "[e1]" not in out
    assert "Tokyo housing market" in out  # prose kept, only the cite stripped


def test_keeps_supported_subset_of_multi_cite() -> None:
    bank = _bank(
        ("e1", "Japan's elderly population will grow sharply through 2050."),
        ("e2", "Antarctic ice sheets are melting at an accelerating rate."),
    )
    # e1 entails, e2 does not.
    out = verify_regen(
        "Japan's elderly population grows sharply toward 2050 [e1][e2].",
        bank, provider=None, entails=lambda c, s: "elderly" in s.lower(),  # type: ignore[arg-type]
    )
    assert "[e1]" in out and "[e2]" not in out


def test_preserves_references_section() -> None:
    bank = _bank(("e1", "Japan's elderly population will grow sharply through 2050."))
    brief = "Japan's elderly population grows toward 2050 [e1].\n\n## References\n\n[e1] T — https://x/e1\n"
    out = verify_regen(brief, bank, provider=None, entails=lambda c, s: False)  # type: ignore[arg-type]
    assert "## References" in out and "https://x/e1" in out


def test_safety_floor_keeps_all_when_every_cite_would_drop() -> None:
    bank = _bank(("e1", "a"), ("e2", "b"), ("e3", "c"))
    brief = "One [e1]. Two [e2]. Three [e3]."
    out = verify_regen(brief, bank, provider=None, entails=lambda c, s: False)  # type: ignore[arg-type]
    assert "[e1]" in out and "[e2]" in out and "[e3]" in out  # systemic-failure guard


def test_budget_cap_keeps_uncheck_ed_cites() -> None:
    bank = _bank(("e1", "x"), ("e2", "y"))
    calls = {"n": 0}

    def counting(_c: str, _s: str) -> bool:
        calls["n"] += 1
        return False

    out = verify_regen(
        "First [e1]. Second [e2].", bank, provider=None,
        entails=counting, max_checks=1,  # type: ignore[arg-type]
    )
    assert calls["n"] == 1
    # e1 checked+dropped, e2 kept unchecked; safety floor doesn't fire (<3 distinct
    # but not all dropped since e2 survives).
    assert "[e2]" in out


def test_empty_brief() -> None:
    assert verify_regen("", _bank(("e1", "x")), provider=None) == ""


# --- regenerate mode (needs a provider) -------------------------------------------


class _FakeProvider:
    """Says 'no' to the original claim, 'yes' after regen; regen returns a canned line."""

    def __init__(self) -> None:
        self.regen_calls = 0

    def complete(self, messages: list[Message], **_: object) -> str:
        system = messages[0].content
        user = messages[1].content
        if "rewrite" in system.lower():  # regen call
            self.regen_calls += 1
            return "Japan's elderly population will grow sharply through 2050."
        # entailment: inspect only the CLAIM (the span always embeds the keyword).
        claim = user.split("SOURCE SPAN:")[0]
        return "yes" if "grow sharply through 2050" in claim else "no"


def test_regenerate_rescues_a_drifted_sentence() -> None:
    bank = _bank(("e1", "Japan's elderly population will grow sharply through 2050."))
    provider = _FakeProvider()
    out = verify_regen(
        "Japan sees big demographic shifts ahead [e1].",
        bank, provider=provider, regenerate=True,  # type: ignore[arg-type]
    )
    assert provider.regen_calls == 1
    assert "[e1]" in out  # cite kept because the rewrite now entails
    assert "grow sharply through 2050" in out  # prose replaced with the faithful restatement
