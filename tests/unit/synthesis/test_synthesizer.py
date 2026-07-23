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
    assert out.startswith("SYNTHESIZED BRIEF")
    assert "## References" in out  # deterministic references always appended
    assert "x improves y" in provider.last_prompt  # evidence passed to model
    assert "does x help?" in provider.last_prompt


def test_synthesizer_empty_sources_returns_empty() -> None:
    assert Synthesizer(FakeProvider()).synthesize([], "q") == ""


def _src_with_url(title: str, url: str | None, claim: str = "finding") -> dict[str, Any]:
    src = _src(title, claim)
    src["full_text_url"] = url
    return src


def test_synthesizer_prompt_asks_for_inline_citations_with_urls() -> None:
    provider = FakeProvider("BRIEF")
    synth = Synthesizer(provider, model="synth")
    synth.synthesize([_src_with_url("A", "https://x.test/a")], query="q")
    assert "https://x.test/a" in provider.last_prompt
    assert "[1]" in provider.last_prompt  # instructed to cite with [n] markers


def test_synthesizer_appends_deterministic_references() -> None:
    provider = FakeProvider("Body text with a claim [1].")
    synth = Synthesizer(provider, model="synth")
    out = synth.synthesize([_src_with_url("Paper A", "https://x.test/a")], query="q")
    assert "## References" in out
    assert "[1] Paper A — https://x.test/a" in out


def test_synthesizer_reference_falls_back_to_paper_url() -> None:
    provider = FakeProvider("Body [1].")
    src = _src_with_url("Paper B", None)
    src["paper"] = {"title": "Paper B", "url": "https://x.test/landing"}
    synth = Synthesizer(provider, model="synth")
    out = synth.synthesize([src], query="q")
    assert "[1] Paper B — https://x.test/landing" in out


def test_synthesizer_keeps_indices_for_urlless_sources() -> None:
    """[n] indices must stay resolvable: urlless sources are listed, not skipped."""
    provider = FakeProvider("Body [1][2].")
    synth = Synthesizer(provider, model="synth")
    out = synth.synthesize(
        [_src_with_url("NoUrl", None), _src_with_url("HasUrl", "https://x.test/b")],
        query="q",
    )
    assert "[1] NoUrl (no URL available)" in out
    assert "[2] HasUrl — https://x.test/b" in out


def test_drop_failed_claims_removes_only_unverified() -> None:
    from research_engine.adversarial.challenge import VerificationResult
    from research_engine.synthesis.synthesizer import drop_failed_claims

    sources = [_src("A", "good claim", "bad claim")]
    verifications = [
        VerificationResult(claim_index=0, source_id="1", claim_text="good claim", ok=True, reason=""),
        VerificationResult(claim_index=1, source_id="1", claim_text="bad claim", ok=False, reason="no evidence"),
    ]
    filtered = drop_failed_claims(sources, verifications)
    claims = [c["claim"] for c in filtered[0]["claims"]]
    assert claims == ["good claim"]


def test_drop_failed_claims_no_verifications_is_noop() -> None:
    from research_engine.synthesis.synthesizer import drop_failed_claims

    sources = [_src("A", "claim x")]
    assert drop_failed_claims(sources, []) == sources


def test_unique_filter_keeps_claimless_source_with_content() -> None:
    """Abstract-only sources often have 0 structured claims but real summaries;
    they must not be silently dropped from synthesis."""
    sources = [
        {"title": "A", "claims": [], "summary": "Population doubles by 2050."},
        {"title": "B", "claims": [{"claim": "x", "evidence": "x"}], "summary": ""},
    ]
    kept = unique_insight_filter(sources)
    assert [s["title"] for s in kept] == ["A", "B"]


def test_unique_filter_dedupes_claimless_sources_by_title() -> None:
    sources = [
        {"title": "Twice as many people in 2050", "claims": [], "summary": "s"},
        {"title": "Twice as many people in 2050", "claims": [], "summary": "s"},
    ]
    assert len(unique_insight_filter(sources)) == 1


def test_unique_filter_drops_empty_source() -> None:
    sources = [{"title": "Empty", "claims": [], "summary": ""}]
    assert unique_insight_filter(sources) == []
