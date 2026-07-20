"""Ephemeral gap rubric (R3): evidence-conditioned gap queries + adaptive-stop verdict."""

from __future__ import annotations

import dataclasses
import json
from typing import Any

from research_engine.planning.gap_rubric import _EVIDENCE_MAX_CHARS, EphemeralGapRubric


class _Provider:
    """Fake LLM provider: records calls, returns a canned reply."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        messages: list[Any],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,
        *,
        request_timeout: float | None = None,
    ) -> str:
        self.calls.append(
            {"messages": messages, "model": model, "request_timeout": request_timeout}
        )
        return self.reply


@dataclasses.dataclass(frozen=True)
class _Span:
    text: str


class _Bank:
    """Duck-typed EvidenceBank: only ``.spans()`` is used by the rubric."""

    def __init__(self, texts: list[str]) -> None:
        self._spans = [_Span(t) for t in texts]

    def spans(self) -> list[_Span]:
        return list(self._spans)


def _reply(gaps: list[str], complete: bool) -> str:
    return json.dumps({"gaps": gaps, "complete": complete})


def test_ingest_parses_gaps_and_incomplete() -> None:
    p = _Provider(_reply(["Norway GPFG allocation", "ADIA asset mix"], False))
    r = EphemeralGapRubric("how govs invest", p, max_queries=5)
    r.ingest(_Bank(["some banked evidence text"]))
    assert r.gap_queries(5) == ["Norway GPFG allocation", "ADIA asset mix"]
    assert r.is_complete() is False
    assert len(p.calls) == 1


def test_gap_queries_capped_by_max_queries() -> None:
    p = _Provider(_reply(["a x", "b y", "c z", "d w"], False))
    r = EphemeralGapRubric("q", p, max_queries=2)
    r.ingest(_Bank(["ev"]))
    assert r.gap_queries(10) == ["a x", "b y"]  # capped to max_queries, not the caller's 10


def test_gap_queries_respects_caller_limit() -> None:
    p = _Provider(_reply(["a x", "b y", "c z"], False))
    r = EphemeralGapRubric("q", p, max_queries=5)
    r.ingest(_Bank(["ev"]))
    assert r.gap_queries(2) == ["a x", "b y"]
    assert r.gap_queries(0) == []


def test_complete_true_with_no_gaps() -> None:
    p = _Provider(_reply([], True))
    r = EphemeralGapRubric("q", p)
    r.ingest(_Bank(["ev"]))
    assert r.gap_queries(5) == []
    assert r.is_complete() is True


def test_complete_ignored_when_gaps_present() -> None:
    # A model that claims complete=true yet lists gaps is not trusted to stop.
    p = _Provider(_reply(["still missing this"], True))
    r = EphemeralGapRubric("q", p, max_queries=3)
    r.ingest(_Bank(["ev"]))
    assert r.gap_queries(5) == ["still missing this"]
    assert r.is_complete() is False


def test_degrades_to_no_gaps_on_garbage() -> None:
    r = EphemeralGapRubric("q", _Provider("not json at all"))
    r.ingest(_Bank(["ev"]))
    assert r.gap_queries(5) == []
    assert r.is_complete() is False  # never a premature stop on parse failure


def test_evidence_is_char_capped_and_timeout_passed() -> None:
    p = _Provider(_reply([], True))
    r = EphemeralGapRubric("q", p)
    r.ingest(_Bank(["x" * 50_000]))  # one huge span
    user_msg = p.calls[-1]["messages"][-1].content
    assert len(user_msg) < _EVIDENCE_MAX_CHARS + 1000  # bounded prompt, not the full 50k
    assert isinstance(p.calls[-1]["request_timeout"], float)  # fast-fail wired
