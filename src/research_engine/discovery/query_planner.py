"""Decompose a research request into source-specific queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_engine.discovery.schema import SourceQuery


@dataclass(frozen=True, slots=True)
class QueryPlan:
    """A plan is a ranked list of source queries plus metadata."""

    queries: list[SourceQuery]
    keywords: list[str]
    rationale: str


class QueryPlanner:
    """Translate a natural-language request into source-specific queries."""

    ACADEMIC_SOURCES = {"semantic_scholar", "crossref", "arxiv", "openalex"}
    WEB_SOURCES = {"serp", "web_crawl"}
    DEFAULT_LIMIT = 10

    def __init__(self, enabled_sources: set[str] | None = None) -> None:
        self.enabled_sources = enabled_sources or set(self.ACADEMIC_SOURCES)

    def plan(self, query: str, context: str = "", max_sources: int = 50) -> QueryPlan:
        """Build a ranked query plan from a research request."""
        if not query or not query.strip():
            raise ValueError("Research query must be non-empty")

        combined = f"{query} {context}".strip()
        keywords = self._extract_keywords(combined)
        queries: list[SourceQuery] = []

        for source in sorted(self.enabled_sources):
            if source in self.ACADEMIC_SOURCES:
                queries.append(
                    SourceQuery(
                        source=source,
                        query=query,
                        rationale=f"Full query against {source} academic index",
                        priority=1,
                    )
                )
                if keywords:
                    queries.append(
                        SourceQuery(
                            source=source,
                            query=" ".join(keywords[:6]),
                            rationale=f"Keyword-focused query against {source}",
                            priority=2,
                        )
                    )
            elif source in self.WEB_SOURCES:
                queries.append(
                    SourceQuery(
                        source=source,
                        query=query,
                        rationale=f"Web search for grey literature and docs via {source}",
                        priority=3,
                    )
                )
            else:
                # Generic source (custom/fake): one full query.
                queries.append(
                    SourceQuery(
                        source=source,
                        query=query,
                        rationale=f"Full query against {source}",
                        priority=1,
                    )
                )

        # Unblocking / problem-solving phrasing.
        if any(kw in query.lower() for kw in ("how to", "find a", "missing", "need a", "cannot find")):
            queries.insert(
                0,
                SourceQuery(
                    source="serp",
                    query=f"{query} tutorial example solution",
                    rationale="Problem-solving query prioritized because the request looks like a blocker",
                    priority=0,
                ),
            )

        return QueryPlan(
            queries=queries,
            keywords=keywords,
            rationale=f"Generated {len(queries)} source-specific queries for: {query[:80]}",
        )

    def _extract_keywords(self, text: str) -> list[str]:
        """Naive keyword extraction: drop stop words and short tokens."""
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "can", "need", "this", "that",
            "these", "those", "i", "you", "he", "she", "it", "we", "they",
            "of", "in", "on", "at", "to", "for", "with", "about", "against",
            "between", "into", "through", "during", "before", "after", "above",
            "below", "from", "up", "down", "out", "off", "over", "under", "again",
            "further", "then", "once", "and", "but", "if", "or", "because",
            "until", "while", "what", "which", "who", "when", "where", "why",
            "how", "all", "any", "both", "each", "few", "more", "most", "other",
            "some", "such", "no", "nor", "not", "only", "own", "same", "so",
            "than", "too", "very", "just", "now",
        }
        words = [
            word.strip(".,;:!?\"'()[]")
            for word in text.lower().split()
            if len(word.strip(".,;:!?\"'()[]")) > 3
            and word.strip(".,;:!?\"'()[]") not in stop_words
        ]
        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for word in words:
            if word not in seen:
                seen.add(word)
                unique.append(word)
        return unique[:12]

    def health(self) -> dict[str, Any]:
        return {"ok": True, "enabled_sources": sorted(self.enabled_sources)}
