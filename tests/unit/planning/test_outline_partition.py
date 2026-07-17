"""W3: Outline.partitioned() — disjoint admissible span sets for section-locked writing."""

from __future__ import annotations

from research_engine.planning.outline import Outline, OutlineSection


def test_partition_dedupes_span_across_sections() -> None:
    outline = Outline(
        sections=(
            OutlineSection("A", "", ("e1", "e2")),
            OutlineSection("B", "", ("e2", "e3")),
        )
    )
    partitioned = outline.partitioned()
    assert partitioned.sections[0].evidence_ids == ("e1", "e2")
    assert partitioned.sections[1].evidence_ids == ("e3",)  # e2 already claimed by A


def test_partition_drops_emptied_section() -> None:
    outline = Outline(
        sections=(OutlineSection("A", "", ("e1",)), OutlineSection("B", "", ("e1",)))
    )
    partitioned = outline.partitioned()
    assert [s.title for s in partitioned.sections] == ["A"]  # B lost its only span → dropped


def test_partition_no_overlap_is_unchanged() -> None:
    outline = Outline(
        sections=(OutlineSection("A", "", ("e1",)), OutlineSection("B", "", ("e2",)))
    )
    assert outline.partitioned() == outline


def test_partition_empty_outline() -> None:
    assert Outline(sections=()).partitioned() == Outline(sections=())
