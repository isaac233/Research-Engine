"""Unit tests for the query planner."""

from __future__ import annotations

import pytest

from research_engine.discovery.query_planner import QueryPlanner


def test_empty_query_raises() -> None:
    planner = QueryPlanner()
    with pytest.raises(ValueError, match="non-empty"):
        planner.plan("")


def test_academic_queries_generated() -> None:
    planner = QueryPlanner()
    plan = planner.plan("systematic review of LLM alignment")
    sources = {q.source for q in plan.queries}
    assert "semantic_scholar" in sources
    assert "crossref" in sources
    assert "arxiv" in sources
    assert "openalex" in sources


def test_keyword_variant_generated() -> None:
    planner = QueryPlanner()
    plan = planner.plan("reinforcement learning from human feedback")
    assert plan.keywords
    keyword_queries = [q for q in plan.queries if "Keyword-focused" in q.rationale]
    assert keyword_queries


def test_blocker_query_prioritizes_serp() -> None:
    planner = QueryPlanner()
    plan = planner.plan("how to find a free dataset for X")
    first = plan.queries[0]
    assert first.source == "serp"
    assert first.priority == 0
    assert "blocker" in first.rationale.lower()


def test_web_sources_respect_enabled_set() -> None:
    planner = QueryPlanner(enabled_sources={"semantic_scholar", "serp"})
    plan = planner.plan("machine learning")
    sources = {q.source for q in plan.queries}
    assert sources == {"semantic_scholar", "serp"}


def test_health_returns_enabled_sources() -> None:
    planner = QueryPlanner(enabled_sources={"arxiv"})
    health = planner.health()
    assert health["ok"] is True
    assert health["enabled_sources"] == ["arxiv"]


def test_non_stem_query_skips_arxiv() -> None:
    """A demographics/market query must not fire keyword noise at arXiv."""
    planner = QueryPlanner()
    plan = planner.plan("elderly demographic market size in Japan 2020-2050")
    sources = {q.source for q in plan.queries}
    assert "arxiv" not in sources
    assert {"crossref", "openalex"} <= sources


def test_stem_query_keeps_arxiv() -> None:
    planner = QueryPlanner()
    plan = planner.plan("efficient routing in sparse mixture-of-experts neural networks")
    assert any(q.source == "arxiv" for q in plan.queries)


def test_arxiv_only_planner_keeps_arxiv_for_any_query() -> None:
    """Never produce an empty plan: sole source is kept even off-domain."""
    planner = QueryPlanner(enabled_sources={"arxiv"})
    plan = planner.plan("elderly demographic market size in Japan 2020-2050")
    assert any(q.source == "arxiv" for q in plan.queries)
