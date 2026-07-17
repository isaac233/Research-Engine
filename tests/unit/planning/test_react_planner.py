"""ReAct research planner (#8): co-evolving outline + iterative gap-driven search."""

from __future__ import annotations

from research_engine.planning.outline import Outline, OutlineSection
from research_engine.planning.react_planner import ReactPlanner, SourceRef


def _text(url: str) -> str:
    # Shares the term "topic" with the query below so the verbatim ranker banks it.
    return f"This verbatim sentence from {url} about the topic has enough length to bank as evidence."


def _fakes(objectives, refs_by_query, *, outline=None):
    """Build a planner over in-memory fakes; return (planner, log)."""
    log: dict = {"refine_digests": [], "reads": [], "summaries": []}

    def objectives_fn(_q):
        return list(objectives)

    def refine_fn(_q, objective, digest):
        log["refine_digests"].append(digest)
        return f"q:{objective}"

    def search_fn(query):
        return list(refs_by_query.get(query, []))

    def read_fn(ref: SourceRef):
        log["reads"].append(ref.url)
        return _text(ref.url)

    def summarize_fn(_q, objective, _text):
        s = f"summary[{objective}]"
        log["summaries"].append(s)
        return s

    def outline_fn(_q, bank):
        if outline is not None:
            return outline
        return Outline(sections=(OutlineSection("Findings", "", tuple(s.id for s in bank.spans())),))

    planner = ReactPlanner(
        objectives_fn=objectives_fn,
        search_fn=search_fn,
        read_fn=read_fn,
        summarize_fn=summarize_fn,
        refine_fn=refine_fn,
        outline_fn=outline_fn,
        max_iters=8,
        max_pages=40,
        per_objective_pages=4,
    )
    return planner, log


def test_iterates_objectives_and_banks_evidence() -> None:
    refs = {
        "q:obj1": [SourceRef("https://a.com", "A")],
        "q:obj2": [SourceRef("https://b.com", "B")],
    }
    planner, log = _fakes(["obj1", "obj2"], refs)
    result = planner.run("the topic")
    assert result.pages_read == 2
    assert set(log["reads"]) == {"https://a.com", "https://b.com"}
    assert not result.evidence_bank.is_empty() if hasattr(result.evidence_bank, "is_empty") else result.evidence_bank.spans()
    assert result.evidence_bank.spans()  # verbatim spans banked from the pages
    assert result.summaries.covered_objectives() == {"obj1", "obj2"}


def test_dedups_urls_across_objectives() -> None:
    shared = SourceRef("https://shared.com", "S")
    refs = {"q:obj1": [shared], "q:obj2": [shared]}
    planner, log = _fakes(["obj1", "obj2"], refs)
    result = planner.run("the topic")
    assert log["reads"] == ["https://shared.com"]  # read exactly once
    assert result.pages_read == 1


def test_summary_digest_feeds_next_refine() -> None:
    refs = {
        "q:obj1": [SourceRef("https://a.com", "A")],
        "q:obj2": [SourceRef("https://b.com", "B")],
    }
    planner, log = _fakes(["obj1", "obj2"], refs)
    planner.run("the topic")
    # First refine sees an empty digest; the second sees obj1's summary.
    assert log["refine_digests"][0] == ""
    assert "summary[obj1]" in log["refine_digests"][1]


def test_max_pages_caps_total_reads() -> None:
    refs = {f"q:obj{i}": [SourceRef(f"https://s{i}.com", "")] for i in range(10)}
    planner, _ = _fakes([f"obj{i}" for i in range(10)], refs)
    planner.max_pages = 3
    result = planner.run("the topic")
    assert result.pages_read == 3


def test_per_objective_page_cap() -> None:
    many = [SourceRef(f"https://a.com/{i}", "") for i in range(10)]
    planner, log = _fakes(["obj1"], {"q:obj1": many})
    planner.per_objective_pages = 2
    result = planner.run("the topic")
    assert result.pages_read == 2


def test_terminates_on_stall_when_all_refs_seen() -> None:
    shared = SourceRef("https://only.com", "")
    refs = {f"q:obj{i}": [shared] for i in range(5)}
    planner, log = _fakes([f"obj{i}" for i in range(5)], refs)
    result = planner.run("the topic")
    # After obj1 reads the only url, later rounds add nothing → stall break.
    assert result.pages_read == 1
    assert result.iterations < 5


def test_dry_first_objective_does_not_abort_the_run() -> None:
    # The first objective's search yields nothing (all 403s / no serp hits in the
    # wild); a later objective is productive. The loop must NOT abort empty on the
    # first dry objective — that regressed react to 0 banked spans in-campaign.
    refs = {"q:obj1": [], "q:obj2": [SourceRef("https://b.com", "B")]}
    planner, log = _fakes(["obj1", "obj2"], refs)
    result = planner.run("the topic")
    assert result.pages_read == 1
    assert log["reads"] == ["https://b.com"]
    assert result.evidence_bank.spans()


def test_empty_objectives_falls_back_to_query() -> None:
    planner, log = _fakes([], {"q:the topic": [SourceRef("https://a.com", "A")]})
    result = planner.run("the topic")
    assert result.pages_read == 1


def test_returns_outline_from_outline_fn() -> None:
    fixed = Outline(sections=(OutlineSection("Custom", "intent", ("e1",)),))
    planner, _ = _fakes(["obj1"], {"q:obj1": [SourceRef("https://a.com", "A")]}, outline=fixed)
    result = planner.run("the topic")
    assert result.outline.sections[0].title == "Custom"


def test_stops_at_wall_clock_deadline() -> None:
    refs = {f"q:obj{i}": [SourceRef(f"https://s{i}.com", "")] for i in range(5)}
    planner, _ = _fakes([f"obj{i}" for i in range(5)], refs)
    # clock: 0 at start, 0 for the first objective's check, then past the 10s budget.
    ticks = iter([0.0, 0.0, 100.0, 100.0, 100.0, 100.0])
    planner.clock = lambda: next(ticks)
    planner.max_seconds = 10.0
    result = planner.run("the topic")
    assert result.pages_read == 1  # only the first objective ran before the deadline
    assert result.iterations == 1


def test_skips_pages_with_empty_text() -> None:
    planner, log = _fakes(["obj1"], {"q:obj1": [SourceRef("https://a.com", "A")]})
    planner.read_fn = lambda _ref: "   "  # type: ignore[assignment]
    result = planner.run("the topic")
    assert result.pages_read == 0


def test_seeded_outline_is_one_section_per_objective_not_evidence_driven() -> None:
    # Lever 1: the QUESTION's dimensions drive the outline (a section per objective,
    # filled with the spans banked FOR that objective) so the report can't drift to
    # whatever topic the banked evidence happens to dominate.
    refs = {
        "q:clothing": [SourceRef("https://cloth.com", "C")],
        "q:transport": [SourceRef("https://trans.com", "T")],
    }
    planner, _ = _fakes(["clothing", "transport"], refs)
    planner.seeded_outline = True
    # Distinct page text per url so the bank does not dedup them to one span.
    bodies = {
        "https://cloth.com": "Elderly clothing spending on the topic rose sharply over the decade.",
        "https://trans.com": "Senior transport demand about the topic shifted toward accessible services.",
    }
    planner.read_fn = lambda ref: bodies[ref.url]  # type: ignore[assignment]
    result = planner.run("the topic")
    titles = [s.title for s in result.outline.sections]
    assert titles == ["clothing", "transport"]  # skeleton = objectives, in order
    # Each section cites only the span banked under its own objective.
    cloth_ids = {s.id for s in result.evidence_bank.spans() if s.url == "https://cloth.com"}
    cloth_section = next(s for s in result.outline.sections if s.title == "clothing")
    assert set(cloth_section.evidence_ids) == cloth_ids


def test_per_objective_searches_retries_until_filled() -> None:
    # Lever 2: a thin objective (first search yields one page) retries a refined
    # search to reach its coverage quota, so no asked dimension stays under-evidenced.
    # refine_fn returns "q:<objective>"; the retry digest differs so we vary the ref map
    # by making the same query return more refs only on the second call.
    calls = {"n": 0}

    def objectives_fn(_q):
        return ["obj1"]

    def refine_fn(_q, _obj, _digest):
        return "q:obj1"

    def search_fn(_query):
        calls["n"] += 1
        # first search: 1 page; second search: a fresh page (retry fills toward quota)
        return [SourceRef(f"https://a.com/{calls['n']}", "")]

    def read_fn(ref):
        return _text(ref.url)

    def summarize_fn(_q, _obj, _t):
        return "s"

    def outline_fn(_q, bank):
        return Outline(sections=(OutlineSection("F", "", tuple(s.id for s in bank.spans())),))

    planner = ReactPlanner(
        objectives_fn=objectives_fn,
        search_fn=search_fn,
        read_fn=read_fn,
        summarize_fn=summarize_fn,
        refine_fn=refine_fn,
        outline_fn=outline_fn,
        per_objective_pages=2,
        per_objective_searches=3,
    )
    result = planner.run("the topic")
    assert result.pages_read == 2  # retried a second search to hit the per-objective quota
    assert calls["n"] == 2
