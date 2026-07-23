"""Tests for the WARP native-loop agent driver (offline; mocked provider + retrieval)."""
from __future__ import annotations

from typing import Any

from research_engine.synthesis.warp_agent import (
    _cited_bibkeys,
    _extract_action,
    _parse_json_action,
    _strip_thought,
    run_warp,
)


def test_extract_action() -> None:
    assert _extract_action("<thought>t</thought><action>{\"name\":\"x\"}</action>") == '{"name":"x"}'
    assert _extract_action("no action here") == ""


def test_parse_json_action_plain_and_trailing_prose() -> None:
    assert _parse_json_action('{"name":"search","keywords":["a"]}') == {
        "name": "search",
        "keywords": ["a"],
    }
    # trailing prose after the JSON is tolerated
    assert _parse_json_action('{"name":"terminate"} done') == {"name": "terminate"}
    assert _parse_json_action("just prose, no json") is None


def test_strip_thought() -> None:
    assert _strip_thought("<think>plan</think>Body") == "Body"
    assert _strip_thought("<thought>x</thought>Real content") == "Real content"


def test_cited_bibkeys() -> None:
    assert _cited_bibkeys(r"text \cite{s1} more \cite{s2, s3}") == {"s1", "s2", "s3"}


class _MockProvider:
    """Returns canned WARP actions keyed by which prompt is being asked."""

    def __init__(self) -> None:
        self.expanded = False

    def complete(self, messages: list[Any], **_: Any) -> str:
        p = messages[0].content
        if "top-level section" in p:  # initialize
            return (
                "<thought>t</thought><action>"
                '{"name":"initialize","title":"SWF Report",'
                '"sections":[{"title":"Intro","plan":"define"},{"title":"Strategy","plan":"how"}]}'
                "</action>"
            )
        if "You are a searcher" in p:
            return '<thought>t</thought><action>{"name":"search","keywords":["swf","strategy"]}</action>'
        if "You are a writer" in p:
            return (
                "<thought>t</thought><action>"
                r"Sovereign wealth funds invest globally \cite{s1} and diversify \cite{s2}."
                "</action>"
            )
        if "needs expansion" in p:  # expand, then terminate
            if not self.expanded:
                self.expanded = True
                return (
                    "<thought>t</thought><action>"
                    '{"name":"expand","position":"section-1","subsections":[{"title":"Deep","plan":"more"}]}'
                    "</action>"
                )
            return '<thought>t</thought><action>{"name":"terminate"}</action>'
        return "<action>x</action>"


def test_full_loop_produces_cited_report() -> None:
    def search_fn(_keywords: list[str]) -> list[str]:
        return ["http://a.example", "http://b.example"]

    def read_fn(url: str) -> str:
        return f"content of {url} about sovereign wealth funds"

    result = run_warp("How do SWFs invest?", _MockProvider(), "m", search_fn, read_fn, max_expands=2)

    assert result.title == "SWF Report"
    # bibkeys s1/s2 (fetched + cited) mapped to [eN]; sources carry the real URLs
    assert "[e1]" in result.markdown and "[e2]" in result.markdown
    assert r"\cite{" not in result.markdown  # all citations converted
    assert len(result.sources) == 2
    assert {s["url"] for s in result.sources} == {"http://a.example", "http://b.example"}
    assert "## References" in result.markdown
    assert result.expands == 1  # expanded once, then terminated
    assert result.actions > 0
