"""Unit tests for V3 cross-source synthesis notes (grounded, FACT-safe)."""

from __future__ import annotations

from typing import Any

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.synthesis.cross_source_notes import build_synthesis_notes


class _FakeProvider:
    """Returns a canned reply (or raises) regardless of the prompt."""

    def __init__(self, reply: str | None = None, boom: bool = False) -> None:
        self._reply = reply or ""
        self._boom = boom

    def complete(self, messages: Any, model: Any = None, **_: Any) -> str:
        if self._boom:
            raise RuntimeError("provider down")
        return self._reply


def _bank(n: int = 4) -> EvidenceBank:
    srcs = [
        {
            "title": "T",
            "paper": {"url": f"https://a.org/{i}", "title": "T"},
            "claims": [{"claim": "c", "evidence": f"Firm {i} invested {i * 100} million in AI research."}],
        }
        for i in range(1, n + 1)
    ]
    return EvidenceBank.from_sources(srcs)


def test_builds_notes_block_from_prose_with_valid_cites() -> None:
    bank = _bank(3)
    ids = [s.id for s in bank.spans()]  # e1..e3
    reply = f"Firm 1 outspent its peers at $100M [{ids[0]}], while Firm 2 lagged [{ids[1]}]."
    notes = build_synthesis_notes(bank, "compare AI spend", _FakeProvider(reply))
    assert notes.startswith("\n\n## Cross-Source Analysis")
    assert f"[{ids[0]}]" in notes and f"[{ids[1]}]" in notes
    assert "outspent" in notes


def test_foreign_cites_stripped() -> None:
    bank = _bank(2)
    ids = [s.id for s in bank.spans()]
    reply = f"A real point [{ids[0]}] and an invented one [e999]."
    notes = build_synthesis_notes(bank, "q", _FakeProvider(reply))
    assert "e999" not in notes  # invented id never survives
    assert f"[{ids[0]}]" in notes


def test_empty_when_no_surviving_cite() -> None:
    # Only a foreign cite -> stripped to nothing citable -> no block (FACT-unsafe).
    bank = _bank(2)
    assert build_synthesis_notes(bank, "q", _FakeProvider("Analysis with a bogus cite [e999].")) == ""


def test_empty_when_reply_has_no_cites() -> None:
    bank = _bank(2)
    assert build_synthesis_notes(bank, "q", _FakeProvider("Pure prose, no citations at all.")) == ""


def test_empty_when_too_few_spans() -> None:
    bank = _bank(1)
    ids = [s.id for s in bank.spans()]
    assert build_synthesis_notes(bank, "q", _FakeProvider(f"Only one [{ids[0]}].")) == ""


def test_degrades_on_provider_failure() -> None:
    assert build_synthesis_notes(_bank(3), "q", _FakeProvider(boom=True)) == ""


def test_empty_reply_returns_empty() -> None:
    assert build_synthesis_notes(_bank(3), "q", _FakeProvider("")) == ""
