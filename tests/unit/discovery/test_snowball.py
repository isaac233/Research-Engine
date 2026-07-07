"""Unit tests for citation snowballing."""

from __future__ import annotations

from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.snowball import SnowballEngine
from research_engine.discovery.sources.base import SourceAdapter


class FakeAdapter(SourceAdapter):
    name = "fake"

    def __init__(self, papers: dict[str, Paper]) -> None:
        self.papers = papers

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        return SearchResult(source=self.name, query=query)

    def fetch_by_id(self, source_id: str) -> Paper | None:
        return self.papers.get(source_id)


def test_expand_follows_citations_out() -> None:
    seed = Paper(
        title="Seed",
        source="fake",
        source_id="seed",
        citations_out=["p1", "p2"],
    )
    p1 = Paper(title="Paper 1", source="fake", source_id="p1")
    p2 = Paper(title="Paper 2", source="fake", source_id="p2")
    engine = SnowballEngine(FakeAdapter({"p1": p1, "p2": p2}), max_depth=1)

    result = engine.expand(seed)
    assert len(result.papers) == 2
    assert {p.title for p in result.papers} == {"Paper 1", "Paper 2"}


def test_expand_follows_citations_in() -> None:
    seed = Paper(
        title="Seed",
        source="fake",
        source_id="seed",
        citations_in=["citer1"],
    )
    citer = Paper(title="Citer", source="fake", source_id="citer1")
    engine = SnowballEngine(FakeAdapter({"citer1": citer}), max_depth=1)

    result = engine.expand(seed)
    assert len(result.papers) == 1
    assert result.papers[0].title == "Citer"


def test_depth_limits_expansion() -> None:
    seed = Paper(
        title="Seed",
        source="fake",
        source_id="seed",
        citations_out=["p1"],
    )
    p1 = Paper(
        title="Paper 1",
        source="fake",
        source_id="p1",
        citations_out=["p2"],
    )
    p2 = Paper(title="Paper 2", source="fake", source_id="p2")

    engine = SnowballEngine(FakeAdapter({"p1": p1, "p2": p2}), max_depth=1)
    result = engine.expand(seed)
    assert len(result.papers) == 1
    assert result.papers[0].title == "Paper 1"

    engine_deep = SnowballEngine(FakeAdapter({"p1": p1, "p2": p2}), max_depth=2)
    result_deep = engine_deep.expand(seed)
    assert len(result_deep.papers) == 2


def test_avoids_revisiting_same_paper() -> None:
    seed = Paper(
        title="Seed",
        source="fake",
        source_id="seed",
        citations_out=["p1", "p2"],
    )
    p1 = Paper(
        title="Paper 1",
        source="fake",
        source_id="p1",
        citations_out=["p2"],
    )
    p2 = Paper(title="Paper 2", source="fake", source_id="p2")

    engine = SnowballEngine(FakeAdapter({"p1": p1, "p2": p2}), max_depth=2)
    result = engine.expand(seed)
    assert len(result.papers) == 2
    assert result.meta["unique_keys"] == 3


def test_max_depth_zero_returns_seed_only() -> None:
    seed = Paper(title="Seed", source="fake", source_id="seed", citations_out=["p1"])
    engine = SnowballEngine(FakeAdapter({}), max_depth=0)
    result = engine.expand(seed)
    assert result.papers == []


def test_missing_neighbor_is_skipped() -> None:
    seed = Paper(
        title="Seed",
        source="fake",
        source_id="seed",
        citations_out=["missing", "p1"],
    )
    p1 = Paper(title="Paper 1", source="fake", source_id="p1")
    engine = SnowballEngine(FakeAdapter({"p1": p1}), max_depth=1)
    result = engine.expand(seed)
    assert len(result.papers) == 1
    assert result.papers[0].title == "Paper 1"
