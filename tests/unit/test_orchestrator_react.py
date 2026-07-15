"""ReAct planner wiring (#8): the orchestrator's live-component closures.

The loop logic is unit-tested in ``test_react_planner``; this guards the glue in
``_react_plan`` — that discovery groups + resolve map become readable SourceRefs,
pages are fetched + banked, and the loop is skipped when the flag is off.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from research_engine.discovery.schema import (
    DiscoveryResult,
    DuplicateGroup,
    Paper,
    ResolveResult,
)
from research_engine.events import EventBus
from research_engine.orchestrator import Orchestrator
from research_engine.state import CampaignStore

_PAGE_HTML = b"<html><body><p>Japan's aging topic population is projected to shrink by 2050.</p></body></html>"


class _DispatchProvider:
    """Route ``complete`` by prompt content so every ReAct LLM step gets valid JSON."""

    name = "fake"

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None, format=None):  # noqa: ANN001
        blob = " ".join(m.content for m in messages).lower()
        if "information objectives" in blob:
            return '{"objectives": [{"objective": "how big is the aging cohort", "query": "japan aging population"}]}'
        if "summarise what this page" in blob or "summarise a source page" in blob:
            return '{"summary": "Japan is aging fast."}'
        if "web search query" in blob:
            return '{"query": "japan aging population size 2050"}'
        if "outline" in blob:
            return '{"sections": [{"title": "Aging", "intent": "", "evidence_ids": ["e1"]}]}'
        return "prose"

    def ping(self):
        return {"ok": True}

    @property
    def default_model(self):
        return "fake"


class _FakeDiscovery:
    def run(self, query, context="", max_sources=10):  # noqa: ANN001
        paper = Paper(title="Aging JP", source="serp", url="https://example.com/aging")
        return DiscoveryResult(
            query=query,
            plan={},
            search_results=[],
            deduped_groups=[DuplicateGroup(canonical=paper)],
            snowball_papers=[],
            resolved=[ResolveResult(paper_key=paper.key, url=paper.url, is_oa=True, source="serp", reason="")],
        )


class _FakeRanker:
    def rank(self, papers, query):  # noqa: ANN001
        return [SimpleNamespace(included=True, paper=p) for p in papers]


class _FakeBrowser:
    def fetch_bytes(self, url):  # noqa: ANN001
        return _PAGE_HTML


def _orch(planner_mode: str) -> Orchestrator:
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(
        store,
        EventBus(store),
        browser=_FakeBrowser(),  # type: ignore[arg-type]
        discovery=_FakeDiscovery(),  # type: ignore[arg-type]
        ranker=_FakeRanker(),  # type: ignore[arg-type]
        synthesizer=SimpleNamespace(provider=_DispatchProvider(), model="fake"),  # type: ignore[arg-type]
    )
    orch.planner_mode = planner_mode
    return orch


def test_react_plan_banks_evidence_from_live_components() -> None:
    orch = _orch("react")
    result = orch._react_plan("aging topic in japan")
    assert result is not None
    assert result.pages_read == 1
    assert result.evidence_bank.spans()  # verbatim spans banked from the fetched page
    assert result.summaries.covered_objectives() == {"how big is the aging cohort"}


def test_react_plan_skipped_when_flag_off() -> None:
    orch = _orch("linear")
    assert orch._react_plan("aging topic") is None
