"""W4: autonomous grounding brief — parse a scoped brief, degrade on failure."""

from __future__ import annotations

from typing import Any

from research_engine.llm.provider import LLMProvider, Message
from research_engine.planning.coverage_ledger import CoverageLedger
from research_engine.planning.grounding_brief import build_grounding_brief


class _Provider(LLMProvider):
    name = "fake"

    def __init__(self, reply: str) -> None:
        self._reply = reply

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
        return self._reply

    def ping(self) -> dict[str, Any]:
        return {}

    @property
    def default_model(self) -> str:
        return "m"


_OK = (
    '{"scope": "sovereign wealth funds of the largest states", '
    '"definitions": [{"term": "SWF", "definition": "sovereign wealth fund"}], '
    '"entities": ["Norway GPFG", "ADIA"], '
    '"section_criteria": ["asset allocation", "governance"]}'
)


def test_brief_parsed_from_json() -> None:
    brief = build_grounding_brief("how do rich govts invest", _Provider(_OK))
    assert brief.entities == ("Norway GPFG", "ADIA")
    assert brief.section_criteria == ("asset allocation", "governance")
    assert brief.definitions == {"SWF": "sovereign wealth fund"}
    assert "sovereign wealth" in brief.scope


def test_brief_degrades_to_query_scope_on_bad_json() -> None:
    brief = build_grounding_brief("my vague query", _Provider("not json at all"))
    assert brief.scope == "my vague query"
    assert brief.entities == ()
    assert brief.section_criteria == ()


def test_brief_degrades_on_provider_error() -> None:
    class Boom(_Provider):
        def complete(self, *a: Any, **k: Any) -> str:
            raise RuntimeError("model down")

    brief = build_grounding_brief("q", Boom(""))
    assert brief.scope == "q" and brief.entities == ()


def test_entities_and_criteria_seed_a_working_ledger() -> None:
    # The whole point: the brief's entities × criteria become the coverage grid.
    brief = build_grounding_brief("q", _Provider(_OK))
    ledger = CoverageLedger(list(brief.entities), list(brief.section_criteria))
    gaps = ledger.gap_queries(10)
    assert "Norway GPFG asset allocation" in gaps  # a concrete, fetchable gap query
