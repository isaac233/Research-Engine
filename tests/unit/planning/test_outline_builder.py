"""Unit tests for the outline generator (Planner/Writer rebuild, Phase 3.1)."""

from __future__ import annotations

import json

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.planning.outline_builder import OutlineBuilder


def _bank() -> EvidenceBank:
    src = {
        "title": "Aging",
        "paper": {"url": "https://a.org", "title": "Aging"},
        "meta": {
            "page_text": (
                "Japan's elderly population reaches 35 percent by 2040 clearly. "
                "Senior consumer spending on housing rises sharply each year. "
                "Transportation demand among the elderly shifts toward accessible services."
            )
        },
        "claims": [],
    }
    return EvidenceBank.from_pages([src], lambda u: "", query="elderly spending")


class _FakeProvider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.last_prompt = ""

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None, format=None):  # noqa: ANN001
        self.last_prompt = messages[-1].content
        return self.reply


def test_builds_outline_from_json() -> None:
    bank = _bank()
    ids = [s.id for s in bank.spans()]
    reply = json.dumps(
        {
            "sections": [
                {"title": "Population", "intent": "size", "evidence_ids": [ids[0]]},
                {"title": "Spending", "intent": "consumption", "evidence_ids": ids[1:]},
            ]
        }
    )
    outline = OutlineBuilder(_FakeProvider(reply)).build(bank, "elderly spending")
    assert [s.title for s in outline.sections] == ["Population", "Spending"]
    assert set(outline.evidence_ids()) <= set(ids)  # only real IDs survive


def test_hallucinated_ids_pruned() -> None:
    bank = _bank()
    real = bank.spans()[0].id
    reply = json.dumps(
        {"sections": [{"title": "X", "intent": "y", "evidence_ids": [real, "e999"]}]}
    )
    outline = OutlineBuilder(_FakeProvider(reply)).build(bank, "q")
    assert "e999" not in outline.evidence_ids()
    assert real in outline.evidence_ids()


def test_json_in_code_fence_parsed() -> None:
    bank = _bank()
    rid = bank.spans()[0].id
    reply = "```json\n" + json.dumps({"sections": [{"title": "T", "intent": "i", "evidence_ids": [rid]}]}) + "\n```"
    outline = OutlineBuilder(_FakeProvider(reply)).build(bank, "q")
    assert outline.sections and outline.sections[0].title == "T"


def test_parse_failure_falls_back_to_single_section() -> None:
    bank = _bank()
    outline = OutlineBuilder(_FakeProvider("not json at all")).build(bank, "q")
    # Fallback: one section citing all spans, so the writer still runs.
    assert len(outline.sections) == 1
    assert set(outline.evidence_ids()) == {s.id for s in bank.spans()}


def test_empty_bank_returns_empty_outline() -> None:
    empty = EvidenceBank.from_sources([])
    outline = OutlineBuilder(_FakeProvider("{}")).build(empty, "q")
    assert outline.sections == ()
