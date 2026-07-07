"""Discovery pipeline: plan, search, dedup, snowball, resolve."""

from __future__ import annotations

from typing import Any

from research_engine.discovery.dedup import DedupEngine
from research_engine.discovery.query_planner import QueryPlanner
from research_engine.discovery.resolver import FullTextResolver
from research_engine.discovery.schema import (
    DiscoveryResult,
    Paper,
    SearchResult,
)
from research_engine.discovery.snowball import SnowballEngine
from research_engine.discovery.source_registry import SourceRegistry
from research_engine.storage.cache import SourceCache


class DiscoveryPipeline:
    """Run the complete discovery stage for a research campaign."""

    def __init__(
        self,
        registry: SourceRegistry | None = None,
        planner: QueryPlanner | None = None,
        dedup: DedupEngine | None = None,
        resolver: FullTextResolver | None = None,
        cache: SourceCache | None = None,
        max_results_per_query: int = 10,
        snowball_depth: int = 1,
        enable_snowball: bool = True,
    ) -> None:
        self.registry = registry or SourceRegistry()
        self.planner = planner or QueryPlanner(enabled_sources=set(self.registry.enabled))
        self.dedup = dedup or DedupEngine()
        self.resolver = resolver or FullTextResolver()
        self.cache = cache
        self.max_results_per_query = max_results_per_query
        self.snowball_depth = snowball_depth
        self.enable_snowball = enable_snowball

    def run(self, query: str, context: str = "", max_sources: int = 50) -> DiscoveryResult:
        """Execute the discovery pipeline."""
        plan = self.planner.plan(query, context=context, max_sources=max_sources)
        search_results: list[SearchResult] = []
        all_papers: list[Paper] = []

        for source_query in plan.queries:
            result = self._search_with_cache(
                source_query.source,
                source_query.query,
            )
            search_results.append(result)
            if result.ok:
                all_papers.extend(result.papers)

        deduped = self.dedup.deduplicate(all_papers)

        snowball_papers: list[Paper] = []
        if self.enable_snowball:
            for group in deduped[:max_sources]:
                engine = SnowballEngine(
                    self.registry.get(group.canonical.source) or next(iter(self.registry.all().values())),
                    dedup=self.dedup,
                    max_depth=self.snowball_depth,
                )
                expansion = engine.expand(group.canonical)
                snowball_papers.extend(expansion.papers)

        # Resolve full text for canonical papers + snowball papers.
        to_resolve = [g.canonical for g in deduped] + snowball_papers
        resolved = [self.resolver.resolve(paper) for paper in to_resolve[:max_sources]]

        return DiscoveryResult(
            query=query,
            plan={
                "queries": [
                    {"source": q.source, "query": q.query, "priority": q.priority}
                    for q in plan.queries
                ],
                "keywords": plan.keywords,
            },
            search_results=search_results,
            deduped_groups=deduped,
            snowball_papers=snowball_papers,
            resolved=resolved,
            meta={
                "raw_paper_count": len(all_papers),
                "canonical_count": len(deduped),
                "snowball_count": len(snowball_papers),
                "resolved_count": len(resolved),
                "cache_enabled": self.cache is not None,
            },
        )

    def _search_with_cache(self, source: str, source_query: str) -> SearchResult:
        """Return cached results when available, otherwise search upstream and cache."""
        if self.cache is not None and self.cache.has(source_query, source):
            cached_papers = self.cache.get_papers(source_query, source)
            return SearchResult(
                source=source,
                query=source_query,
                papers=cached_papers,
                total=len(cached_papers),
                meta={"cached": True},
            )

        result = self.registry.search(
            source,
            source_query,
            limit=self.max_results_per_query,
        )
        if self.cache is not None and result.ok and result.papers:
            self.cache.put(source_query, source, result.papers)
        return result

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "registry": self.registry.health(),
            "planner": self.planner.health(),
            "cache_enabled": self.cache is not None,
        }
