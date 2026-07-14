"""Unit tests for the research Outline (Planner/Writer rebuild, Phase 3.1)."""

from __future__ import annotations

from research_engine.planning.outline import Outline, OutlineSection


def _outline() -> Outline:
    return Outline(
        sections=(
            OutlineSection(title="Population", intent="How many elderly", evidence_ids=("e1", "e2")),
            OutlineSection(title="Spending", intent="Consumption potential", evidence_ids=("e3",)),
        )
    )


def test_json_round_trip() -> None:
    o = _outline()
    o2 = Outline.from_dict(o.to_dict())
    assert o2 == o
    assert [s.title for s in o2.sections] == ["Population", "Spending"]
    assert o2.sections[0].evidence_ids == ("e1", "e2")


def test_evidence_ids_unique_ordered() -> None:
    o = Outline(
        sections=(
            OutlineSection("A", "i", ("e1", "e2")),
            OutlineSection("B", "i", ("e2", "e3")),  # e2 repeats
        )
    )
    assert o.evidence_ids() == ("e1", "e2", "e3")


def test_pruned_drops_unknown_ids() -> None:
    o = _outline()  # cites e1,e2,e3
    pruned = o.pruned({"e1", "e3"})  # e2 unknown -> dropped
    assert pruned.sections[0].evidence_ids == ("e1",)
    assert pruned.sections[1].evidence_ids == ("e3",)


def test_pruned_drops_sections_left_without_evidence() -> None:
    o = _outline()
    pruned = o.pruned({"e3"})  # only Spending keeps evidence
    assert [s.title for s in pruned.sections] == ["Spending"]


def test_empty_outline() -> None:
    assert Outline(sections=()).evidence_ids() == ()
    assert Outline.from_dict({"sections": []}).sections == ()
