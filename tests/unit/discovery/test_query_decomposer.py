"""LLM query decomposition — turn one task into many facet sub-queries (evidence volume)."""

from __future__ import annotations

import json

from research_engine.discovery.query_decomposer import decompose_query


class _Provider:
    def __init__(self, reply: str) -> None:
        self.reply = reply

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
        return self.reply


def test_decompose_returns_subqueries() -> None:
    reply = json.dumps(
        {"queries": ["japan elderly population 2050", "japan senior consumer spending", "japan aging housing market"]}
    )
    subs = decompose_query("elderly market in Japan", _Provider(reply), None, n=8)
    assert len(subs) == 3
    assert "japan elderly population 2050" in subs


def test_dedupes_and_caps() -> None:
    reply = json.dumps({"queries": ["a", "a", "b", "c", "d", "e"]})
    subs = decompose_query("q", _Provider(reply), None, n=3)
    assert subs == ["a", "b", "c"]  # deduped, capped at n


def test_parse_failure_falls_back_to_original() -> None:
    subs = decompose_query("original query", _Provider("not json"), None, n=8)
    assert subs == ["original query"]


def test_no_provider_returns_original() -> None:
    assert decompose_query("q", None, None) == ["q"]
