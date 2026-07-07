"""End-to-end campaign test with mocked external sources."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import (
    DiscoveryResult,
    DuplicateGroup,
    Paper,
    ResolveResult,
    SearchResult,
)
from research_engine.main import cli


def _fake_discovery_run(_self: DiscoveryPipeline, query: str, **kwargs: object) -> DiscoveryResult:
    """Return a synthetic discovery result with one includable paper."""
    paper = Paper(
        title="Synthetic LLM Review Paper",
        authors=["A. Researcher"],
        year=2024,
        doi="10.1234/example",
        url="https://example.com/paper",
        pdf_url="https://example.com/paper.pdf",
        abstract="Our results show that the proposed method improves LLM review coverage by 20%.",
        source="semantic_scholar",
        source_id="synth-1",
    )
    return DiscoveryResult(
        query=query,
        plan={"queries": [{"source": "semantic_scholar", "query": query, "priority": 1}], "keywords": []},
        search_results=[
            SearchResult(source="semantic_scholar", query=query, papers=[paper], total=1)
        ],
        deduped_groups=[DuplicateGroup(canonical=paper)],
        snowball_papers=[],
        resolved=[ResolveResult(paper_key=paper.key, url=None, is_oa=False, source="resolver", reason="mock")],
    )


def test_e2e_research_campaign_writes_insights(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(DiscoveryPipeline, "run", _fake_discovery_run)

    runner = CliRunner()
    query = "recent methods in LLM systematic literature reviews"
    result = runner.invoke(cli, ["--project-root", str(tmp_path), "run", query])

    assert result.exit_code == 0, result.output

    slug = "recent_methods_in_llm_systematic_literature_review"  # derived by state slugify
    campaign_insights = tmp_path / "Research" / slug / f"{slug}_Insights.MD"
    master_insights = tmp_path / "Research" / "Insights.MD"

    assert campaign_insights.exists(), f"Campaign brief not found at {campaign_insights}"
    assert master_insights.exists(), f"Master brief not found at {master_insights}"

    brief_text = campaign_insights.read_text(encoding="utf-8")
    assert brief_text.strip()
    assert "Synthetic LLM Review Paper" in brief_text or "claim" in brief_text.lower()
