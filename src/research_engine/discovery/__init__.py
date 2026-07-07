"""Discovery package: query planning, source adapters, dedup, snowball, resolver."""

from research_engine.discovery.query_planner import QueryPlanner
from research_engine.discovery.schema import Paper, SearchResult, SourceQuery
from research_engine.discovery.sources.base import SourceAdapter

__all__ = ["Paper", "SearchResult", "SourceQuery", "SourceAdapter", "QueryPlanner"]
