"""Coverage ledger (DualGraph-lite, W2): an entity×sub-question matrix whose empty or
weak cells drive targeted gap queries.

Outline-only planning (rebuild-the-outline-each-round) gives weak supervision for
knowledge gaps: the agent elaborates what it already banked instead of finding what's
missing — the dropped-dimensions failure on vague queries (task 53). DualGraph
(arXiv:2602.13830, RACE 53.08) fixes this with a knowledge graph whose topology exposes
gaps; this is its lightweight form. A fixed grid of (entity, sub-question) cells is
ingested from the evidence bank each round, spans are assigned to cells by term overlap,
and the cells that are empty or weakly supported emit a bounded set of concrete gap
queries ("Norway GPFG asset allocation") for the next retrieval round.

Entities and sub-questions come from the grounding brief (W4); with no entities the grid
is empty and the ledger is a no-op, so it only bites once scope has been established.
"""

from __future__ import annotations

import dataclasses

from research_engine.memory.evidence_bank import EvidenceBank, _terms


@dataclasses.dataclass(frozen=True, slots=True)
class Cell:
    """One (entity, sub-question) coverage cell and the span IDs that fill it."""

    entity: str
    subquestion: str
    span_ids: tuple[str, ...]


class CoverageLedger:
    """Track which (entity, sub-question) pairs have evidence; emit gap queries."""

    def __init__(
        self, entities: list[str], subquestions: list[str], *, weak_below: int = 2
    ) -> None:
        self._entities = [e.strip() for e in entities if e.strip()]
        self._subquestions = [q.strip() for q in subquestions if q.strip()]
        self.weak_below = max(1, weak_below)
        self._entity_terms = {e: _terms(e) for e in self._entities}
        self._subq_terms = {q: _terms(q) for q in self._subquestions}
        self._cells: dict[tuple[str, str], set[str]] = {
            (e, q): set() for e in self._entities for q in self._subquestions
        }

    def ingest(self, bank: EvidenceBank) -> None:
        """Assign each span to every cell whose entity AND sub-question it mentions.

        Recomputed from scratch each call (the bank is cumulative) so repeated ingests
        across rounds are idempotent rather than double-counting.
        """
        for key in self._cells:
            self._cells[key] = set()
        for span in bank.spans():
            span_terms = _terms(span.text)
            if not span_terms:
                continue
            for entity in self._entities:
                if not (self._entity_terms[entity] & span_terms):
                    continue
                for subq in self._subquestions:
                    if self._subq_terms[subq] & span_terms:
                        self._cells[(entity, subq)].add(span.id)

    def cells(self) -> list[Cell]:
        """The full grid with each cell's assigned span IDs (sorted, deterministic)."""
        return [
            Cell(entity, subq, tuple(sorted(ids)))
            for (entity, subq), ids in self._cells.items()
        ]

    def gap_queries(self, max_queries: int) -> list[str]:
        """Up to ``max_queries`` concrete queries for empty cells first, then weak ones."""
        if max_queries <= 0 or not self._cells:
            return []
        empty = [k for k, ids in self._cells.items() if not ids]
        weak = [k for k, ids in self._cells.items() if 0 < len(ids) < self.weak_below]
        return [f"{entity} {subq}" for entity, subq in (empty + weak)[:max_queries]]

    def is_complete(self) -> bool:
        """True when the grid is non-empty and every cell meets the weak threshold."""
        return bool(self._cells) and all(
            len(ids) >= self.weak_below for ids in self._cells.values()
        )
