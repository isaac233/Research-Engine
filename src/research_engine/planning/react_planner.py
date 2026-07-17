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
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.memory.summary_bank import SummaryBank, SummaryNote
from research_engine.planning.outline import Outline, OutlineSection

if TYPE_CHECKING:
    from research_engine.planning.coverage_ledger import CoverageLedger

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


def _page_dict(ref: SourceRef, text: str, objective: str = "") -> dict[str, Any]:
    """Shape a read page as an ``ExtractedSource``-like dict for ``EvidenceBank``.

    ``objective`` tags which decomposition objective banked this page, so a task-seeded
    outline can group each objective's spans into its own section (Lever 1).
    """
    return {
        "title": ref.title,
        "paper": {"url": ref.url, "title": ref.title},
        "meta": {"page_text": text, "objective": objective},
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
        per_objective_searches: int = 1,
        seeded_outline: bool = False,
        coverage_ledger: CoverageLedger | None = None,
        max_seconds: float | None = None,
        clock: Callable[[], float] = time.monotonic,
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
        # Lever 2 (balanced retrieval): a thin objective retries a refined search up to
        # this many times to reach its per-objective quota, so every asked dimension
        # gets evidence instead of the budget piling onto the dominant serp topic.
        self.per_objective_searches = per_objective_searches
        # Lever 1 (task-seeded skeleton): when set, the final outline is one section per
        # objective (filled with that objective's spans) instead of the LLM rebuild that
        # drifts to the banked evidence's dominant topic.
        self.seeded_outline = seeded_outline
        # Coverage ledger (W2, DualGraph-lite): when set, each round ingests the bank
        # into an entity×sub-question grid and appends gap queries for empty/weak cells
        # as new objectives, so under-covered dimensions get targeted retrieval instead
        # of the loop drifting to the dominant topic. None = the loop is unchanged.
        self.coverage_ledger = coverage_ledger
        # Hard wall-clock budget: a live run must never hang. When exceeded the loop
        # stops with whatever it has banked (the writer still gets an outline+bank).
        self.max_seconds = max_seconds
        self.clock = clock

    def run(self, query: str) -> PlanResult:
        """Execute the loop for ``query`` and return the filled banks + outline."""
        objectives = list(self.objectives_fn(query) or [query])
        seen_objectives = set(objectives)
        summaries = SummaryBank()
        pages: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        bank = EvidenceBank([])
        iterations = 0
        start = self.clock()

        outline = Outline(sections=())
        for objective in objectives:
            over_budget = self.max_seconds is not None and self.clock() - start > self.max_seconds
            if iterations >= self.max_iters or len(pages) >= self.max_pages or over_budget:
                break
            iterations += 1
            added = self._collect(query, objective, pages, seen_urls, summaries)
            if added == 0:
                # A dry objective (no serp hits / every candidate 403s or is already
                # seen) must not abort the whole run before anything is banked — that
                # regressed react to 0 spans in-campaign whenever the FIRST objective
                # happened to be unfetchable. Only stop early once we already have
                # evidence (the query space is genuinely exhausting); otherwise move
                # on to the next objective, which may well be fetchable.
                if pages:
                    break
                continue
            # Co-evolve: rebuild the bank + outline from the evidence gathered so far
            # so the structure tracks the growing evidence, not the opening decomposition.
            bank = EvidenceBank.from_pages(pages, lambda _u: "", query, max_fetches=0)
            outline = self.outline_fn(query, bank)
            # W2: expose coverage gaps as new objectives so under-covered (entity,
            # sub-question) cells get targeted retrieval. Bounded per round and deduped,
            # so it converges rather than looping (max_iters/max_pages still bind).
            if self.coverage_ledger is not None:
                try:
                    self.coverage_ledger.ingest(bank)
                    gaps = self.coverage_ledger.gap_queries(max(1, self.max_iters // 4))
                except Exception:  # noqa: BLE001 — a ledger fault must not abort the plan
                    gaps = []
                for gap in gaps:
                    if gap not in seen_objectives:
                        seen_objectives.add(gap)
                        objectives.append(gap)

        if self.seeded_outline and pages:
            bank = EvidenceBank.from_pages(pages, lambda _u: "", query, max_fetches=0)
            outline = self._seed_outline(objectives, pages, bank) or outline
        return PlanResult(bank, outline, summaries, list(pages), len(pages), iterations)

    def _seed_outline(
        self, objectives: list[str], pages: list[dict[str, Any]], bank: EvidenceBank
    ) -> Outline | None:
        """Lever 1: one outline section per objective, filled with that objective's
        banked spans — so the report follows the task's dimensions, not the evidence's
        dominant topic. Returns None (caller keeps the co-evolved outline) if nothing
        maps, so an all-unmapped run never yields an empty outline."""
        url_objective = {
            p["paper"]["url"]: p.get("meta", {}).get("objective", "") for p in pages
        }
        section_ids: dict[str, list[str]] = {}
        for span in bank.spans():
            objective = url_objective.get(span.url, "")
            section_ids.setdefault(objective, []).append(span.id)
        # Preserve objective order; drop dupes; skip objectives that banked no spans.
        seen: set[str] = set()
        sections = []
        for objective in objectives:
            if objective in seen or not section_ids.get(objective):
                continue
            seen.add(objective)
            sections.append(OutlineSection(objective, objective, tuple(section_ids[objective])))
        return Outline(sections=tuple(sections)) if sections else None

    def _collect(
        self,
        query: str,
        objective: str,
        pages: list[dict[str, Any]],
        seen_urls: set[str],
        summaries: SummaryBank,
    ) -> int:
        """Read toward ``per_objective_pages`` new pages for one objective, retrying a
        refined search up to ``per_objective_searches`` times so a thin objective still
        reaches its quota (Lever 2). Returns how many were actually banked (0 = stall)."""
        added = 0
        for _ in range(max(1, self.per_objective_searches)):
            refined = self.refine_fn(query, objective, summaries.digest())
            added += self._read_one_search(
                query, objective, refined, pages, seen_urls, summaries, added
            )
            if added >= self.per_objective_pages or len(pages) >= self.max_pages:
                break
        return added

    def _read_one_search(
        self,
        query: str,
        objective: str,
        refined_query: str,
        pages: list[dict[str, Any]],
        seen_urls: set[str],
        summaries: SummaryBank,
        already_added: int,
    ) -> int:
        """Read new fetchable pages from one search; return how many were banked."""
        added = 0
        for ref in self.search_fn(refined_query):
            if len(pages) >= self.max_pages or already_added + added >= self.per_objective_pages:
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
            pages.append(_page_dict(ref, text, objective))
            added += 1
        return added
