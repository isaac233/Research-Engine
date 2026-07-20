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


# --- R1: evidence-grounded scope (finish_line_execution_v9) --------------------


def test_collect_scope_evidence_reads_bounded_unique_pages() -> None:
    from research_engine.orchestrator import _collect_scope_evidence

    refs = [SimpleNamespace(url=f"https://e/{i}", title=f"T{i}") for i in range(6)]
    reads: dict[str, int] = {}

    def read_fn(ref):  # noqa: ANN001
        reads[ref.url] = reads.get(ref.url, 0) + 1
        return f"body of {ref.url}"

    ev = _collect_scope_evidence("q", lambda q: refs, read_fn, max_pages=3, snippet_chars=1000)
    assert len(reads) == 3  # stopped at the page budget
    assert "body of https://e/0" in ev


def test_collect_scope_evidence_skips_empty_and_dupes() -> None:
    from research_engine.orchestrator import _collect_scope_evidence

    refs = [
        SimpleNamespace(url="https://a", title="A"),
        SimpleNamespace(url="https://a", title="A"),  # duplicate url
        SimpleNamespace(url="https://b", title="B"),  # empty read
        SimpleNamespace(url="https://c", title="C"),
    ]

    def read_fn(ref):  # noqa: ANN001
        return "" if ref.url == "https://b" else f"body {ref.url}"

    ev = _collect_scope_evidence("q", lambda q: refs, read_fn, max_pages=5, snippet_chars=1000)
    assert ev.count("body") == 2  # a and c; dupe + empty dropped
    assert "https://b" not in ev


def test_collect_scope_evidence_caps_snippet_chars() -> None:
    from research_engine.orchestrator import _collect_scope_evidence

    ref = SimpleNamespace(url="https://a", title="A")
    ev = _collect_scope_evidence("q", lambda q: [ref], lambda r: "y" * 2000, max_pages=3, snippet_chars=50)
    assert "y" * 50 in ev
    assert "y" * 51 not in ev


def _spy_build_rubric(monkeypatch, captured):  # noqa: ANN001
    import research_engine.orchestrator as orch_mod

    real = orch_mod.build_rubric

    def spy(query, provider, model=None, evidence=""):  # noqa: ANN001
        captured["evidence"] = evidence
        return real(query, provider, model, evidence=evidence)

    monkeypatch.setattr(orch_mod, "build_rubric", spy)


def test_scoping_pass_disabled_by_default_no_grounding(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_RUBRIC_SCAFFOLD", "1")  # rubric on, scoping off
    captured: dict[str, str] = {}
    _spy_build_rubric(monkeypatch, captured)
    _orch("react")._react_plan("how wealthiest governments invest")
    assert captured["evidence"] == ""  # blind scope preserved (A path)


def test_scoping_pass_grounds_rubric_when_enabled(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_RUBRIC_SCAFFOLD", "1")
    monkeypatch.setenv("RESEARCH_ENGINE_SCOPING_PASS", "1")
    captured: dict[str, str] = {}
    _spy_build_rubric(monkeypatch, captured)
    _orch("react")._react_plan("how wealthiest governments invest")
    assert captured["evidence"]  # non-empty — scope grounded in the fetched page (B path)
    assert "population" in captured["evidence"].lower()


# --- R2: verified checklist critic wiring --------------------------------------


def _spy_critique(monkeypatch, called):  # noqa: ANN001
    import research_engine.orchestrator as orch_mod

    def spy(rubric, provider, model=None):  # noqa: ANN001
        called["n"] += 1
        return rubric

    monkeypatch.setattr(orch_mod, "critique_rubric", spy)


def test_rubric_critic_disabled_by_default(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_RUBRIC_SCAFFOLD", "1")  # critic flag off
    called = {"n": 0}
    _spy_critique(monkeypatch, called)
    _orch("react")._react_plan("how wealthiest governments invest")
    assert called["n"] == 0


def test_rubric_critic_runs_when_enabled(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_RUBRIC_SCAFFOLD", "1")
    monkeypatch.setenv("RESEARCH_ENGINE_RUBRIC_CRITIC", "1")
    called = {"n": 0}
    _spy_critique(monkeypatch, called)
    _orch("react")._react_plan("how wealthiest governments invest")
    assert called["n"] == 1


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


# --- P1 persistent rubric scaffold (DuMate test-time rubric) -----------------

import json as _json  # noqa: E402


class _RubricProvider(_DispatchProvider):
    """Serves a rubric for the rubric prompt; everything else as _DispatchProvider."""

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None, format=None, request_timeout=None):  # noqa: ANN001
        blob = " ".join(m.content for m in messages).lower()
        if "rubric-plan" in blob:
            return _json.dumps(
                {
                    "title": "Sovereign Wealth Investment Strategies",
                    "scope": "The largest state investment funds.",
                    "sections": ["Fund Cohort and Scale", "Asset Allocation Patterns"],
                    "guidance": ["Define the cohort explicitly"],
                }
            )
        return super().complete(messages, model, temperature, max_tokens, format)


def test_rubric_sections_become_objectives_when_enabled(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_RUBRIC_SCAFFOLD", "1")
    store = CampaignStore(Path(tempfile.mkdtemp()) / "state.db")
    orch = Orchestrator(
        store, EventBus(store),
        browser=_FakeBrowser(),  # type: ignore[arg-type]
        discovery=_FakeDiscovery(),  # type: ignore[arg-type]
        ranker=_FakeRanker(),  # type: ignore[arg-type]
        synthesizer=SimpleNamespace(provider=_RubricProvider(), model="fake"),  # type: ignore[arg-type]
    )
    orch.planner_mode = "react"
    # Query terms must overlap the fixture page (span banking is query-ranked).
    # The single-URL fixture dries up after objective 1, so only the FIRST rubric
    # section can complete — what matters is that rubric sections, not the default
    # plan_objectives decomposition, drive the loop.
    result = orch._react_plan("aging topic in japan")
    assert result is not None
    covered = result.summaries.covered_objectives()
    assert "Fund Cohort and Scale" in covered
    assert "how big is the aging cohort" not in covered
    assert orch._rubric.title == "Sovereign Wealth Investment Strategies"
    assert "Define the cohort explicitly" in orch._rubric.digest()


def test_rubric_off_keeps_default_objectives(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_RUBRIC_SCAFFOLD", raising=False)
    orch = _orch("react")
    result = orch._react_plan("aging topic in japan")
    assert result is not None
    assert result.summaries.covered_objectives() == {"how big is the aging cohort"}
    assert orch._rubric.title == ""  # trivial rubric ⇒ writer path unchanged


# --- Wayback last-resort read fallback (fetchability lever, P2) --------------


class _BlockedExceptWayback:
    """403s every direct read but serves archive.org snapshots."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_bytes(self, url):  # noqa: ANN001
        self.calls.append(url)
        if url.startswith("https://web.archive.org/"):
            return b"<html><body><p>Archived snapshot content.</p></body></html>"
        raise RuntimeError("HTTP error 403")


def test_fetch_page_text_wayback_after_cdp_miss(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_CDP_FALLBACK", "1")
    monkeypatch.setenv("RESEARCH_ENGINE_WAYBACK_FALLBACK", "1")
    orch = _orch("react")
    fake_browser = _BlockedExceptWayback()
    orch.browser = fake_browser  # type: ignore[assignment]
    miss = _FakeCDP("", ok=False, error="blocked")  # CDP also fails
    monkeypatch.setattr(orch, "_ensure_cdp", lambda: miss)
    text = orch._fetch_page_text("https://blocked.example/x")
    assert "Archived snapshot content" in text
    assert fake_browser.calls[-1] == "https://web.archive.org/web/2/https://blocked.example/x"


def test_fetch_page_text_wayback_without_cdp(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_CDP_FALLBACK", raising=False)
    monkeypatch.setenv("RESEARCH_ENGINE_WAYBACK_FALLBACK", "1")
    orch = _orch("react")
    orch.browser = _BlockedExceptWayback()  # type: ignore[assignment]
    text = orch._fetch_page_text("https://blocked.example/x")
    assert "Archived snapshot content" in text


def test_fetch_page_text_wayback_miss_returns_empty(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_CDP_FALLBACK", raising=False)
    monkeypatch.setenv("RESEARCH_ENGINE_WAYBACK_FALLBACK", "1")
    orch = _orch("react")
    orch.browser = _Blocked()  # type: ignore[assignment]  # blocks archive.org too
    assert orch._fetch_page_text("https://blocked.example/x") == ""


def test_fetch_page_text_no_wayback_when_flag_off(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_CDP_FALLBACK", raising=False)
    monkeypatch.delenv("RESEARCH_ENGINE_WAYBACK_FALLBACK", raising=False)
    orch = _orch("react")
    orch.browser = _BlockedExceptWayback()  # type: ignore[assignment]
    import pytest

    with pytest.raises(RuntimeError):  # byte-identical legacy behavior
        orch._fetch_page_text("https://blocked.example/x")


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
