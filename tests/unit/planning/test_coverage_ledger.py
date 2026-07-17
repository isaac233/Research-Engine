"""W2: coverage ledger (DualGraph-lite) — cell assignment + gap queries."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank, EvidenceSpan
from research_engine.planning.coverage_ledger import CoverageLedger


def _span(sid: str, text: str) -> EvidenceSpan:
    return EvidenceSpan(id=sid, text=text, url=f"http://{sid}", title="", verifiable=True)


def _bank(*spans: EvidenceSpan) -> EvidenceBank:
    return EvidenceBank(list(spans))


def test_ingest_assigns_span_by_term_overlap() -> None:
    ledger = CoverageLedger(["Norway"], ["allocation"], weak_below=1)
    ledger.ingest(_bank(_span("e1", "Norway sovereign fund allocation rose sharply")))
    cell = next(c for c in ledger.cells() if c.entity == "Norway" and c.subquestion == "allocation")
    assert cell.span_ids == ("e1",)


def test_span_missing_a_term_is_not_assigned() -> None:
    ledger = CoverageLedger(["Norway"], ["allocation"], weak_below=1)
    # mentions the entity but not the sub-question term → cell stays empty
    ledger.ingest(_bank(_span("e1", "Norway governance structure overview")))
    cell = next(c for c in ledger.cells() if c.entity == "Norway")
    assert cell.span_ids == ()


def test_empty_cell_emits_gap_query() -> None:
    ledger = CoverageLedger(["Norway", "Singapore"], ["returns"], weak_below=1)
    ledger.ingest(_bank(_span("e1", "Norway returns were strong this year")))
    gaps = ledger.gap_queries(10)
    assert "Singapore returns" in gaps  # the uncovered cell
    assert "Norway returns" not in gaps  # covered → silent


def test_weak_cell_below_threshold_emits_gap_query() -> None:
    ledger = CoverageLedger(["Norway"], ["returns"], weak_below=2)
    ledger.ingest(_bank(_span("e1", "Norway returns rose")))  # 1 span < weak_below 2
    assert "Norway returns" in ledger.gap_queries(10)


def test_strong_cell_is_silent() -> None:
    ledger = CoverageLedger(["Norway"], ["returns"], weak_below=2)
    ledger.ingest(
        _bank(_span("e1", "Norway returns rose"), _span("e2", "Norway returns climbed again"))
    )
    assert ledger.gap_queries(10) == []


def test_gap_queries_bounded_by_max() -> None:
    ledger = CoverageLedger(["A", "B", "C"], ["x"], weak_below=1)
    ledger.ingest(_bank())  # all empty
    assert len(ledger.gap_queries(2)) == 2


def test_empty_cells_prioritized_over_weak() -> None:
    ledger = CoverageLedger(["Cov", "Emp"], ["topic"], weak_below=2)
    ledger.ingest(_bank(_span("e1", "Cov topic mentioned once")))  # Cov weak, Emp empty
    first = ledger.gap_queries(1)
    assert first == ["Emp topic"]  # empty cell wins the single slot


def test_is_complete_when_all_cells_meet_threshold() -> None:
    ledger = CoverageLedger(["Norway"], ["returns"], weak_below=1)
    assert ledger.is_complete() is False
    ledger.ingest(_bank(_span("e1", "Norway returns rose")))
    assert ledger.is_complete() is True


def test_ingest_is_idempotent_across_rounds() -> None:
    ledger = CoverageLedger(["Norway"], ["returns"], weak_below=1)
    bank = _bank(_span("e1", "Norway returns rose"))
    ledger.ingest(bank)
    ledger.ingest(bank)  # same bank again → no double count
    cell = next(c for c in ledger.cells() if c.entity == "Norway")
    assert cell.span_ids == ("e1",)


def test_no_entities_is_a_noop() -> None:
    ledger = CoverageLedger([], ["returns"])
    ledger.ingest(_bank(_span("e1", "anything returns here")))
    assert ledger.gap_queries(10) == []
    assert ledger.is_complete() is False
