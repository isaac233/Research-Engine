"""Summary Bank — the planner-context half of the split memory bank (#9)."""

from __future__ import annotations

from research_engine.memory.summary_bank import SummaryBank, SummaryNote


def test_add_and_notes_roundtrip() -> None:
    bank = SummaryBank()
    bank.add(SummaryNote(url="https://a.com", title="A", objective="obj1", summary="A says X."))
    bank.add(SummaryNote(url="https://b.com", title="B", objective="obj2", summary="B says Y."))
    assert len(bank.notes()) == 2
    assert bank.urls() == {"https://a.com", "https://b.com"}


def test_dedup_by_url_keeps_first() -> None:
    bank = SummaryBank()
    bank.add(SummaryNote(url="https://a.com", title="A", objective="o", summary="first"))
    bank.add(SummaryNote(url="https://a.com", title="A2", objective="o", summary="second"))
    assert len(bank.notes()) == 1
    assert bank.notes()[0].summary == "first"


def test_digest_concatenates_title_and_summary() -> None:
    bank = SummaryBank()
    bank.add(SummaryNote(url="https://a.com", title="Aging Japan", objective="o", summary="Pop declines."))
    digest = bank.digest()
    assert "Aging Japan" in digest
    assert "Pop declines." in digest


def test_digest_respects_max_chars() -> None:
    bank = SummaryBank()
    for i in range(50):
        bank.add(SummaryNote(url=f"https://a.com/{i}", title=f"T{i}", objective="o", summary="x" * 200))
    digest = bank.digest(max_chars=500)
    assert len(digest) <= 500


def test_empty_bank() -> None:
    bank = SummaryBank()
    assert bank.is_empty()
    assert bank.digest() == ""
    assert bank.urls() == set()


def test_covered_objectives_tracks_distinct() -> None:
    bank = SummaryBank()
    bank.add(SummaryNote(url="https://a.com", title="A", objective="obj1", summary="s"))
    bank.add(SummaryNote(url="https://b.com", title="B", objective="obj1", summary="s"))
    bank.add(SummaryNote(url="https://c.com", title="C", objective="obj2", summary="s"))
    assert bank.covered_objectives() == {"obj1", "obj2"}
