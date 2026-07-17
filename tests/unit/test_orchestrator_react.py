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

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None, format=None, request_timeout=None):  # noqa: ANN001
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


def test_extract_short_circuits_for_react_when_skip_collect_set(monkeypatch) -> None:  # noqa: ANN001
    # The react planner does its own retrieval at evaluate-time; the linear extract is
    # an unused fallback that double-pays the slowest stage. With the flag set it must
    # be skipped (no extraction work) so react runs are practical.
    from research_engine.state import ResearchRequest

    monkeypatch.setenv("RESEARCH_ENGINE_REACT_SKIP_COLLECT", "1")
    orch = _orch("react")
    campaign = orch.start_campaign(ResearchRequest(query="aging topic", max_sources=5))
    result = orch._run_extract(campaign)
    assert "react planner owns retrieval" in str(result).lower()


def test_extract_not_skipped_for_linear_even_with_flag(monkeypatch) -> None:  # noqa: ANN001
    # The skip is react-only; a linear campaign must still extract (no fallback loss).
    from research_engine.state import ResearchRequest

    monkeypatch.setenv("RESEARCH_ENGINE_REACT_SKIP_COLLECT", "1")
    orch = _orch("linear")
    campaign = orch.start_campaign(ResearchRequest(query="aging topic", max_sources=5))
    result = orch._run_extract(campaign)
    assert "react planner owns retrieval" not in str(result).lower()


class _RecordingProvider(_DispatchProvider):
    """Record the model each reasoning step was called with."""

    def __init__(self) -> None:
        self.models: dict[str, str] = {}

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None, format=None, request_timeout=None):  # noqa: ANN001
        blob = " ".join(m.content for m in messages).lower()
        if "information objectives" in blob:
            self.models["objectives"] = model
        elif "summarise" in blob:
            self.models["summarise"] = model
        elif "web search query" in blob:
            self.models["refine"] = model
        elif "outline" in blob:
            self.models["outline"] = model
        return super().complete(messages, model, temperature, max_tokens, format)


def test_reasoning_model_env_routes_reasoning_steps(monkeypatch) -> None:  # noqa: ANN001
    # Hybrid Phase 0.1: the reasoning seams use the override model; unset ⇒ synth model.
    monkeypatch.setenv("RESEARCH_ENGINE_REACT_REASONING_MODEL", "tongyi-test")
    provider = _RecordingProvider()
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(
        store, EventBus(store),
        browser=_FakeBrowser(),  # type: ignore[arg-type]
        discovery=_FakeDiscovery(),  # type: ignore[arg-type]
        ranker=_FakeRanker(),  # type: ignore[arg-type]
        synthesizer=SimpleNamespace(provider=provider, model="fake"),  # type: ignore[arg-type]
    )
    orch.planner_mode = "react"
    orch._react_plan("aging topic in japan")
    assert provider.models.get("objectives") == "tongyi-test"
    assert provider.models.get("summarise") == "tongyi-test"
    assert provider.models.get("refine") == "tongyi-test"
    assert provider.models.get("outline") == "tongyi-test"


def test_reasoning_model_defaults_to_synth_model_when_unset(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_REACT_REASONING_MODEL", raising=False)
    provider = _RecordingProvider()
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(
        store, EventBus(store),
        browser=_FakeBrowser(),  # type: ignore[arg-type]
        discovery=_FakeDiscovery(),  # type: ignore[arg-type]
        ranker=_FakeRanker(),  # type: ignore[arg-type]
        synthesizer=SimpleNamespace(provider=provider, model="fake"),  # type: ignore[arg-type]
    )
    orch.planner_mode = "react"
    orch._react_plan("aging topic in japan")
    assert provider.models.get("objectives") == "fake"  # byte-identical to single-model path


# --- CDP 403-recovery fallback (retrieval fetchability lever) ---------------

from research_engine.browser.ai_browser import BrowserResult  # noqa: E402


class _Blocked:
    """A byte-fetcher that always bot-blocks (the ~50% of live reads returning 403)."""

    def fetch_bytes(self, url):  # noqa: ANN001
        raise RuntimeError("HTTP error 403")


class _FakeCDP:
    """Stand-in CDP driver — records fetches, returns rendered HTML, tracks close."""

    def __init__(self, html: str, ok: bool = True, error: str = "") -> None:
        self.html = html
        self.ok = ok
        self.error = error
        self.calls: list[str] = []
        self.closed = False

    def act(self, action):  # noqa: ANN001
        self.calls.append(action.url)
        return BrowserResult(
            ok=self.ok, action=action.action, url=action.url,
            status=200 if self.ok else 403, content=self.html, error=self.error,
        )

    def close(self) -> None:
        self.closed = True


def test_fetch_page_text_recovers_403_via_cdp_when_enabled(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_CDP_FALLBACK", "1")
    orch = _orch("react")
    orch.browser = _Blocked()  # type: ignore[assignment]
    fake = _FakeCDP("<html><body><p>Recovered 2050 census figure.</p></body></html>")
    monkeypatch.setattr(orch, "_ensure_cdp", lambda: fake)
    text = orch._fetch_page_text("https://blocked.example/x")
    assert "Recovered 2050 census figure" in text
    assert fake.calls == ["https://blocked.example/x"]


def test_fetch_page_text_no_cdp_when_flag_off(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_CDP_FALLBACK", raising=False)
    orch = _orch("react")
    orch.browser = _Blocked()  # type: ignore[assignment]
    consulted: list[int] = []
    monkeypatch.setattr(orch, "_ensure_cdp", lambda: consulted.append(1))
    # Flag off ⇒ behavior byte-identical to today: the 403 propagates to read_fn.
    import pytest

    with pytest.raises(RuntimeError):
        orch._fetch_page_text("https://blocked.example/x")
    assert consulted == []


def test_fetch_page_text_skips_cdp_when_raw_ok(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_CDP_FALLBACK", "1")
    orch = _orch("react")  # _FakeBrowser returns a healthy page
    consulted: list[int] = []
    monkeypatch.setattr(orch, "_ensure_cdp", lambda: consulted.append(1))
    text = orch._fetch_page_text("https://example.com/aging")
    assert "aging topic population" in text
    assert consulted == []  # healthy raw fetch never launches Chromium


def test_react_plan_closes_cdp_driver(monkeypatch) -> None:  # noqa: ANN001
    # The Chromium process must be closed after the react window so bench tasks
    # don't leak a browser each (50 tasks ⇒ 50 zombie Chromiums otherwise).
    monkeypatch.setenv("RESEARCH_ENGINE_CDP_FALLBACK", "1")
    orch = _orch("react")
    fake = _FakeCDP("<html></html>")
    orch._cdp = fake  # type: ignore[assignment]
    orch._react_plan("aging topic in japan")
    assert fake.closed is True


# --- W3 section-locked write (ADORE memory-locked synthesis) -----------------

import research_engine.orchestrator as _orch_mod  # noqa: E402


def test_section_locked_write_skips_deepen(monkeypatch) -> None:  # noqa: ANN001
    # Under the lock, the whole-bank deepen pass is skipped (it would re-introduce
    # cross-section spans and defeat the disjoint admissible sets).
    monkeypatch.setenv("RESEARCH_ENGINE_SECTION_LOCKED_WRITE", "1")
    called: list[int] = []
    monkeypatch.setattr(_orch_mod, "deepen_report", lambda *a, **k: called.append(1) or "x")
    orch = _orch("react")
    orch._react_brief("aging topic in japan")
    assert called == []  # deepen not called under the lock


def test_default_write_calls_deepen(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_SECTION_LOCKED_WRITE", raising=False)
    called: list[int] = []
    original = _orch_mod.deepen_report
    monkeypatch.setattr(
        _orch_mod, "deepen_report", lambda *a, **k: (called.append(1), original(*a, **k))[1]
    )
    orch = _orch("react")
    orch._react_brief("aging topic in japan")
    assert called  # deepen runs on the default (unlocked) path
