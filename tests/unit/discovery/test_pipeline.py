"""Unit tests for the discovery pipeline."""

from __future__ import annotations

from pathlib import Path

from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.source_registry import SourceRegistry
from research_engine.discovery.sources.base import SourceAdapter
from research_engine.storage.cache import SourceCache


class FakeAdapter(SourceAdapter):
    name = "fake"

    def __init__(self, papers: list[Paper]) -> None:
        self.papers = papers
        self.search_calls = 0

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        self.search_calls += 1
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


def _fake_registry(papers: list[Paper]) -> tuple[SourceRegistry, FakeAdapter]:
    registry = SourceRegistry(enabled={"fake"})
    adapter = FakeAdapter(papers)
    registry._adapters["fake"] = adapter
    return registry, adapter


def test_pipeline_cache_skips_upstream_on_second_run(tmp_path: Path) -> None:
    papers = [Paper(title="Cached", source="fake", source_id="1", doi="10.1/cached")]
    registry, adapter = _fake_registry(papers)
    cache = SourceCache(tmp_path / "cache.db")
    pipeline = DiscoveryPipeline(registry=registry, cache=cache, enable_snowball=False)

    pipeline.run("cache query")
    first_calls = adapter.search_calls

    pipeline.run("cache query")
    assert adapter.search_calls == first_calls, "cache hit should not call adapter again"


def test_pipeline_cache_stores_results_on_miss(tmp_path: Path) -> None:
    papers = [Paper(title="Fresh", source="fake", source_id="1", doi="10.1/fresh")]
    registry, adapter = _fake_registry(papers)
    cache = SourceCache(tmp_path / "cache.db")
    pipeline = DiscoveryPipeline(registry=registry, cache=cache, enable_snowball=False)

    assert not cache.has("fresh query", "fake")
    result = pipeline.run("fresh query")
    assert result.meta["cache_enabled"] is True
    assert cache.has("fresh query", "fake")
    assert len(cache.get_papers("fresh query", "fake")) == 1
