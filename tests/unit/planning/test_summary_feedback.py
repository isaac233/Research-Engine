"""Summary-feedback loop (#7): page -> summary, and summaries -> next sub-query."""

from __future__ import annotations

import json

from research_engine.planning.summary_feedback import refine_query, summarize_page


class _Provider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list = []

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None, format=None, request_timeout=None):  # noqa: ANN001
        self.calls.append(messages)
        return self.reply


def test_summarize_page_uses_llm() -> None:
    prov = _Provider(json.dumps({"summary": "Japan's population is aging fast."}))
    out = summarize_page("aging japan", "how big is the elderly cohort", "Long page text...", prov, None)
    assert out == "Japan's population is aging fast."


def test_summarize_page_no_provider_falls_back_to_excerpt() -> None:
    page = "First sentence about aging. Second sentence with more. Third one here."
    out = summarize_page("q", "o", page, None, None)
    assert out  # non-empty extractive fallback
    assert out.startswith("First sentence")


def test_summarize_page_empty_text_returns_empty() -> None:
    assert summarize_page("q", "o", "   ", _Provider("{}"), None) == ""


def test_summarize_page_parse_failure_falls_back_to_excerpt() -> None:
    out = summarize_page("q", "o", "Some readable page content here.", _Provider("not json"), None)
    assert out.startswith("Some readable page")


def test_refine_query_uses_llm_and_digest() -> None:
    prov = _Provider(json.dumps({"query": "japan elderly healthcare spending 2050"}))
    out = refine_query("japan aging", "healthcare costs of aging", "Learned: pop declines.", prov, None)
    assert out == "japan elderly healthcare spending 2050"
    # The digest was fed to the model.
    assert any("pop declines" in m.content.lower() for msgs in prov.calls for m in msgs)


def test_refine_query_no_provider_falls_back_to_objective() -> None:
    assert refine_query("q", "the objective text", "digest", None, None) == "the objective text"


def test_refine_query_parse_failure_falls_back_to_objective() -> None:
    assert refine_query("q", "obj", "digest", _Provider("garbage"), None) == "obj"
