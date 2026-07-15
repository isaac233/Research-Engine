"""ReAct research planner (#8): a dynamic outline that co-evolves with iterative,
gap-driven search — the breadth engine that closes the ~10x evidence gap to
WebWeaver.

The linear pipeline does ONE discovery pass, so the report is capped by whatever
happened to be fetched first. This planner instead:

1. enumerates the report's information objectives BEFORE retrieval (the coverage
   target — "Don't Stop Early", arXiv:2604.24978);
2. loops over the uncovered objectives, refining each search query from what's
   already been learned (summary-feedback, #7), reading new pages, banking their
   verbatim spans (writer memory) and short summaries (planner memory, #9);
3. rebuilds the outline from the growing evidence bank each round, so the
   structure co-evolves with the evidence instead of being fixed up front;
4. terminates on evidence-based signals — every objective covered, a per-task page
   budget, or a round that adds nothing new (stall).

It is pure orchestration over injected callables (search / read / summarise /
refine / outline), so the whole loop is unit-testable with in-memory fakes and the
live wiring (discovery, extraction, Ollama) is supplied by the orchestrator behind
a default-off flag.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from typing import Any

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.memory.summary_bank import SummaryBank, SummaryNote
from research_engine.planning.outline import Outline

# Injected-callable signatures.
ObjectivesFn = Callable[[str], list[str]]
SearchFn = Callable[[str], "list[SourceRef]"]
ReadFn = Callable[["SourceRef"], str]
SummarizeFn = Callable[[str, str, str], str]  # (query, objective, page_text) -> summary
RefineFn = Callable[[str, str, str], str]  # (query, objective, digest) -> query
OutlineFn = Callable[[str, EvidenceBank], Outline]  # (query, bank) -> outline


@dataclasses.dataclass(frozen=True, slots=True)
class SourceRef:
    """A candidate page the planner may read: its URL and (optional) title."""

    url: str
    title: str = ""


@dataclasses.dataclass(frozen=True, slots=True)
class PlanResult:
    """What the loop produced: the two memory halves, the outline, and run stats.

    ``pages`` are the read pages as ``ExtractedSource``-like dicts (each carrying
    ``meta.page_text``), so the orchestrator can feed them straight into the
    existing evaluate path without re-fetching.
    """

    evidence_bank: EvidenceBank
    outline: Outline
    summaries: SummaryBank
    pages: list[dict[str, Any]]
    pages_read: int
    iterations: int


def _page_dict(ref: SourceRef, text: str) -> dict[str, Any]:
    """Shape a read page as an ``ExtractedSource``-like dict for ``EvidenceBank``."""
    return {
        "title": ref.title,
        "paper": {"url": ref.url, "title": ref.title},
        "meta": {"page_text": text},
    }


class ReactPlanner:
    """Drive the objective-covering, outline-co-evolving research loop."""

    def __init__(
        self,
        *,
        objectives_fn: ObjectivesFn,
        search_fn: SearchFn,
        read_fn: ReadFn,
        summarize_fn: SummarizeFn,
        refine_fn: RefineFn,
        outline_fn: OutlineFn,
        max_iters: int = 8,
        max_pages: int = 40,
        per_objective_pages: int = 4,
    ) -> None:
        self.objectives_fn = objectives_fn
        self.search_fn = search_fn
        self.read_fn = read_fn
        self.summarize_fn = summarize_fn
        self.refine_fn = refine_fn
        self.outline_fn = outline_fn
        self.max_iters = max_iters
        self.max_pages = max_pages
        self.per_objective_pages = per_objective_pages

    def run(self, query: str) -> PlanResult:
        """Execute the loop for ``query`` and return the filled banks + outline."""
        objectives = self.objectives_fn(query) or [query]
        summaries = SummaryBank()
        pages: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        bank = EvidenceBank([])
        iterations = 0

        for objective in objectives:
            if iterations >= self.max_iters or len(pages) >= self.max_pages:
                break
            iterations += 1
            refined = self.refine_fn(query, objective, summaries.digest())
            added = self._collect(query, objective, refined, pages, seen_urls, summaries)
            # Co-evolve: rebuild the outline from the evidence gathered so far so the
            # structure tracks the growing bank (not just the opening decomposition).
            bank = EvidenceBank.from_pages(pages, lambda _u: "", query, max_fetches=0)
            if added == 0:
                # A round that surfaces nothing new means this query space is
                # exhausted — stop rather than burn budget on empty repeats.
                break

        outline = self.outline_fn(query, bank)
        return PlanResult(bank, outline, summaries, list(pages), len(pages), iterations)

    def _collect(
        self,
        query: str,
        objective: str,
        refined_query: str,
        pages: list[dict[str, Any]],
        seen_urls: set[str],
        summaries: SummaryBank,
    ) -> int:
        """Read up to ``per_objective_pages`` new pages for one objective; return
        how many were actually banked (0 signals a stalled query space)."""
        added = 0
        for ref in self.search_fn(refined_query):
            if len(pages) >= self.max_pages or added >= self.per_objective_pages:
                break
            if ref.url in seen_urls:
                continue
            text = self.read_fn(ref)
            if not text.strip():
                continue
            seen_urls.add(ref.url)
            summary = self.summarize_fn(query, objective, text)
            summaries.add(
                SummaryNote(url=ref.url, title=ref.title, objective=objective, summary=summary)
            )
            pages.append(_page_dict(ref, text))
            added += 1
        return added
