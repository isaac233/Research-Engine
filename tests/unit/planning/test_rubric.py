"""Persistent rubric generation (P1 DuMate-style scaffold)."""

from __future__ import annotations

import json

from research_engine.llm.provider import Message
from research_engine.planning.rubric import TRIVIAL, build_rubric


class _Provider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[list[Message]] = []

    def complete(self, messages, model=None, temperature=0.7, max_tokens=None, **kw):  # noqa: ANN001, ANN003
        self.calls.append(messages)
        return self.reply


def test_build_rubric_parses_fields() -> None:
    reply = json.dumps(
        {
            "title": "Global Sovereign Wealth Investment Strategies",
            "scope": "The ten largest sovereign wealth funds and state pension funds.",
            "sections": ["Definition and Cohort", "Asset Allocation Patterns"],
            "guidance": ["Define the cohort explicitly", "Give quantitative allocations"],
        }
    )
    r = build_rubric("how the wealthiest governments invest", _Provider(reply))
    assert r.title.startswith("Global Sovereign")
    assert r.sections == ("Definition and Cohort", "Asset Allocation Patterns")
    assert len(r.guidance) == 2
    assert "Scope:" in r.digest() and "Quality criteria:" in r.digest()


def test_build_rubric_degrades_to_trivial_on_garbage() -> None:
    r = build_rubric("q", _Provider("not json at all"))
    assert r == TRIVIAL
    assert r.digest() == ""


def test_build_rubric_caps_lists() -> None:
    reply = json.dumps(
        {
            "title": "T",
            "scope": "S",
            "sections": [f"S{i}" for i in range(20)],
            "guidance": [f"G{i}" for i in range(20)],
        }
    )
    r = build_rubric("q", _Provider(reply))
    assert len(r.sections) == 10
    assert len(r.guidance) == 8
