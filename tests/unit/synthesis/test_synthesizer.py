"""Unit tests for the synthesizer + unique-insight filter."""

from __future__ import annotations

from typing import Any

from research_engine.llm.provider import LLMProvider, Message
from research_engine.synthesis.synthesizer import Synthesizer, unique_insight_filter


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, response: str = "BRIEF") -> None:
        self._response = response
        self.last_prompt = ""

    def complete(
        self, messages: list[Message], model: str | None = None,
        temperature: float = 0.7, max_tokens: int | None = None,
    ) -> str:
        self.last_prompt = messages[-1].content
        return self._response

    def ping(self) -> dict[str, Any]:
        return {"ok": True}

    @property
    def default_model(self) -> str:
        return "fake"


def _src(title: str, *claims: str) -> dict[str, Any]:
    return {"title": title, "claims": [{"claim": c, "evidence": c} for c in claims]}


def test_unique_filter_drops_duplicate_insight_sources() -> None:
    sources = [
        _src("A", "method X improves accuracy"),
        _src("B", "method X improves accuracy"),  # same insight -> dropped
        _src("C", "method Y reduces latency"),
    ]
    kept = unique_insight_filter(sources)
    titles = [s["title"] for s in kept]
    assert titles == ["A", "C"]


def test_unique_filter_respects_target_volume() -> None:
    sources = [_src("A", "a1"), _src("B", "b1"), _src("C", "c1")]
    assert len(unique_insight_filter(sources, target_volume=2)) == 2


def test_synthesizer_renders_sources_and_returns_brief() -> None:
    provider = FakeProvider("SYNTHESIZED BRIEF")
    synth = Synthesizer(provider, model="synth")
    out = synth.synthesize([_src("A", "x improves y")], query="does x help?")
    assert out == "SYNTHESIZED BRIEF"
    assert "x improves y" in provider.last_prompt  # evidence passed to model
    assert "does x help?" in provider.last_prompt


def test_synthesizer_empty_sources_returns_empty() -> None:
    assert Synthesizer(FakeProvider()).synthesize([], "q") == ""
