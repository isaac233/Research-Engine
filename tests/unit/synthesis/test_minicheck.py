"""W1: MiniCheck check-fn factory — backend selection + Yes/No mapping."""

from __future__ import annotations

from typing import Any

from research_engine.llm.provider import LLMProvider, Message
from research_engine.synthesis.minicheck import build_check_fn


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.seen: list[tuple[list[Message], str | None]] = []

    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,
        *,
        request_timeout: float | None = None,
    ) -> str:
        self.seen.append((messages, model))
        return self._reply

    def ping(self) -> dict[str, Any]:
        return {}

    @property
    def default_model(self) -> str:
        return "m"


def test_unknown_spec_returns_none() -> None:
    assert build_check_fn("", provider=FakeProvider("Yes")) is None
    assert build_check_fn("bogus", provider=FakeProvider("Yes")) is None


def test_minicheck_requires_provider() -> None:
    assert build_check_fn("minicheck", provider=None) is None


def test_minicheck_ollama_yes_maps_to_1() -> None:
    prov = FakeProvider("Yes")
    fn = build_check_fn("minicheck", provider=prov)
    assert fn is not None
    assert fn("some document text", "a claim") == 1.0
    # the model got the Document/Claim template and the bespoke-minicheck model id
    (messages, model) = prov.seen[0]
    assert model == "bespoke-minicheck"
    assert "Document:" in messages[0].content and "Claim:" in messages[0].content


def test_minicheck_ollama_no_maps_to_0() -> None:
    fn = build_check_fn("minicheck", provider=FakeProvider("No"))
    assert fn is not None
    assert fn("doc", "claim") == 0.0


def test_flan_missing_dependency_returns_none() -> None:
    # pip `minicheck` (torch/transformers) is not installed in the unit env → graceful None,
    # never a crash. If it ever IS installed this still must not raise.
    result = build_check_fn("flan")
    assert result is None or callable(result)
