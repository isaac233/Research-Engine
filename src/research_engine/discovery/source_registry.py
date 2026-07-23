"""Registry of enabled discovery source adapters."""

from __future__ import annotations

from typing import Any

from research_engine.discovery.schema import SearchResult
from research_engine.discovery.sources.arxiv import ArxivAdapter
from research_engine.discovery.sources.base import SourceAdapter
from research_engine.discovery.sources.crossref import CrossrefAdapter
from research_engine.discovery.sources.openalex import OpenAlexAdapter
from research_engine.discovery.sources.semantic_scholar import SemanticScholarAdapter
from research_engine.discovery.sources.serp import SERPAdapter
from research_engine.discovery.sources.web_crawl import WebCrawlAdapter


class SourceRegistry:
    """Build and hold discovery source adapters."""

    DEFAULT_SOURCES: tuple[str, ...] = (
        "semantic_scholar",
        "crossref",
        "arxiv",
        "openalex",
    )

    def __init__(
        self,
        enabled: set[str] | None = None,
        s2_api_key: str | None = None,
        crossref_mailto: str | None = None,
        openalex_mailto: str | None = None,
        serp_endpoint: str | None = None,
        serp_blocklist: tuple[str, ...] = (),
    ) -> None:
        self.enabled = enabled or set(self.DEFAULT_SOURCES)
        self._adapters: dict[str, SourceAdapter] = {}
        self._s2_api_key = s2_api_key
        self._crossref_mailto = crossref_mailto
        self._openalex_mailto = openalex_mailto
        self._serp_endpoint = serp_endpoint
        self._serp_blocklist = serp_blocklist

    def get(self, source: str) -> SourceAdapter | None:
        if source not in self.enabled:
            return None
        if source not in self._adapters:
            self._adapters[source] = self._build(source)
        return self._adapters.get(source)

    def search(self, source: str, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        adapter = self.get(source)
        if adapter is None:
            return SearchResult(
                source=source,
                query=query,
                error=f"Source '{source}' not enabled",
            )
        return adapter.search(query, limit=limit, offset=offset)

    def all(self) -> dict[str, SourceAdapter]:
        for source in sorted(self.enabled):
            self.get(source)
        return dict(self._adapters)

    def _build(self, source: str) -> SourceAdapter:
        if source == "semantic_scholar":
            return SemanticScholarAdapter(api_key=self._s2_api_key)
        if source == "crossref":
            return CrossrefAdapter(mailto=self._crossref_mailto)
        if source == "arxiv":
            return ArxivAdapter()
        if source == "openalex":
            return OpenAlexAdapter(mailto=self._openalex_mailto)
        if source == "serp":
            return SERPAdapter(
                endpoint=self._serp_endpoint, blocklist=self._serp_blocklist
            )
        if source == "web_crawl":
            return WebCrawlAdapter()
        raise ValueError(f"Unknown discovery source: {source}")

    def health(self) -> dict[str, Any]:
        return {
            "ok": True,
            "enabled": sorted(self.enabled),
            "adapter_health": {name: adapter.health() for name, adapter in self.all().items()},
        }
