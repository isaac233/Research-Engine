"""Unit tests for the discovery pipeline."""

from __future__ import annotations

from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.source_registry import SourceRegistry
from research_engine.discovery.sources.base import SourceAdapter


class FakeAdapter(SourceAdapter):
    name = "fake"

    def __init__(self, papers: list[Paper]) -> None:
        self.papers = papers

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        return SearchResult(
            source=self.name,
            query=query,
            papers=self.papers,
        )

    def fetch_by_id(self, source_id: str) -> Paper | None:
        for paper in self.papers:
            if paper.source_id == source_id:
                return paper
        return None


def test_pipeline_runs_all_steps() -> None:
    papers = [
        Paper(title="Alpha", source="fake", source_id="1", doi="10.1/alpha"),
        Paper(title="Beta", source="fake", source_id="2", doi="10.1/beta"),
    ]
    registry = SourceRegistry(enabled={"fake"})
    registry._adapters["fake"] = FakeAdapter(papers)
    pipeline = DiscoveryPipeline(registry=registry, enable_snowball=False)

    result = pipeline.run("test query")

    assert result.query == "test query"
    assert len(result.search_results) >= 1
    assert len(result.deduped_groups) == 2
    assert len(result.resolved) == 2
    assert result.meta["canonical_count"] == 2


def test_pipeline_deduplicates_across_searches() -> None:
    papers = [
        Paper(title="Alpha", source="fake", source_id="1", doi="10.1/alpha"),
        Paper(title="Alpha", source="fake", source_id="2", doi="10.1/alpha"),
    ]
    registry = SourceRegistry(enabled={"fake"})
    registry._adapters["fake"] = FakeAdapter(papers)
    pipeline = DiscoveryPipeline(registry=registry, enable_snowball=False)

    result = pipeline.run("alpha")
    assert len(result.deduped_groups) == 1
    assert len(result.deduped_groups[0].duplicates) == 1


def test_pipeline_respects_max_sources() -> None:
    papers = [
        Paper(title=f"Paper {i}", source="fake", source_id=str(i), doi=f"10.test/{i}")
        for i in range(20)
    ]
    registry = SourceRegistry(enabled={"fake"})
    registry._adapters["fake"] = FakeAdapter(papers)
    pipeline = DiscoveryPipeline(registry=registry, enable_snowball=False)

    result = pipeline.run("many papers", max_sources=5)
    assert len(result.resolved) == 5


def test_pipeline_snowball_adds_papers() -> None:
    seed = Paper(
        title="Seed",
        source="fake",
        source_id="seed",
        citations_out=["child"],
    )
    child = Paper(title="Child", source="fake", source_id="child")
    registry = SourceRegistry(enabled={"fake"})
    registry._adapters["fake"] = FakeAdapter([seed, child])
    pipeline = DiscoveryPipeline(registry=registry, enable_snowball=True, snowball_depth=1)

    result = pipeline.run("seed")
    assert len(result.snowball_papers) == 1
    assert result.snowball_papers[0].title == "Child"
