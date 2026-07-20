"""Persistent rubric generation (P1 DuMate-style scaffold)."""

from __future__ import annotations

import json

from research_engine.llm.provider import Message
from research_engine.planning.rubric import (
    _EVIDENCE_MAX_CHARS,
    _USER,
    TRIVIAL,
    build_rubric,
    critique_rubric,
)


class _Provider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[list[Message]] = []

    def complete(self, messages, model=None, temperature=0.7, max_tokens=None, **kw):  # noqa: ANN001, ANN003
        self.calls.append(messages)
        return self.reply

    def _last_user(self) -> str:
        return self.calls[-1][1].content


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


# --- R1: evidence-grounded scope (finish_line_execution_v9) --------------------

_GOOD = json.dumps(
    {"title": "T", "scope": "S", "sections": ["A", "B"], "guidance": ["g1", "g2"]}
)


def test_build_rubric_evidence_default_prompt_byte_identical() -> None:
    # No evidence → the user prompt is exactly today's blind template (A path unchanged).
    p = _Provider(_GOOD)
    build_rubric("wealthiest governments invest", p)
    assert p._last_user() == _USER.format(query="wealthiest governments invest")


def test_build_rubric_conditions_scope_on_evidence() -> None:
    p = _Provider(_GOOD)
    build_rubric(
        "wealthiest governments invest",
        p,
        evidence="Norway's GPFG is the largest SWF.\n\nADIA manages ~$1T.",
    )
    msg = p._last_user()
    assert "Norway's GPFG is the largest SWF." in msg
    assert "ADIA manages ~$1T." in msg


def test_build_rubric_evidence_uses_self_clarification_framing() -> None:
    p = _Provider(_GOOD)
    build_rubric("q", p, evidence="some scoping evidence")
    assert "ambiguous" in p._last_user().lower()


def test_build_rubric_evidence_still_degrades_to_trivial_on_garbage() -> None:
    r = build_rubric("q", _Provider("not json at all"), evidence="some evidence")
    assert r == TRIVIAL


def test_build_rubric_evidence_is_char_capped() -> None:
    p = _Provider(_GOOD)
    big = "x" * (_EVIDENCE_MAX_CHARS + 500)
    build_rubric("q", p, evidence=big)
    msg = p._last_user()
    assert "x" * _EVIDENCE_MAX_CHARS in msg  # kept up to the cap
    assert big not in msg  # but truncated (not the full over-cap string)


# --- R2: verified checklist critic (finish_line_execution_v9) -------------------


def _vague_rubric():  # noqa: ANN202
    return build_rubric(
        "q",
        _Provider(
            json.dumps(
                {"title": "T", "scope": "Rich governments.", "sections": ["A", "B"], "guidance": ["g"]}
            )
        ),
    )


def test_critique_rubric_tightens_scope_and_adds_acceptance() -> None:
    tightened = json.dumps(
        {
            "title": "T2",
            "scope": "The ten largest SWFs by AUM (excludes public pension funds).",
            "sections": ["A", "B"],
            "guidance": ["Acceptance: each section cites AUM figures", "Compare funds"],
        }
    )
    r = critique_rubric(_vague_rubric(), _Provider(tightened))
    assert "ten largest SWFs" in r.scope
    assert "excludes" in r.scope.lower()
    assert any("acceptance" in g.lower() for g in r.guidance)


def test_critique_rubric_degrades_to_input_on_garbage() -> None:
    vague = _vague_rubric()
    r = critique_rubric(vague, _Provider("not json at all"))
    assert r == vague  # unchanged — never TRIVIAL, never raises


def test_critique_rubric_noop_on_trivial() -> None:
    p = _Provider(json.dumps({"title": "x", "scope": "y", "sections": ["z"], "guidance": ["g"]}))
    r = critique_rubric(TRIVIAL, p)
    assert r == TRIVIAL
    assert p.calls == []  # no LLM call spent on a trivial rubric
