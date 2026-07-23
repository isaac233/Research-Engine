"""Unit tests for the R6 evidence-ranking critic."""

from __future__ import annotations

import json

from research_engine.memory.evidence_bank import EvidenceSpan
from research_engine.planning.evidence_ranker import SpanScore, rank_spans


class _ScoringProvider:
    """Return a deterministic JSON score table."""

    name = "fake"

    def __init__(self, scores: list[SpanScore]) -> None:
        self.scores = scores
        self.calls: list[dict[str, str]] = []

    def complete(
        self,
        messages,
        model=None,
        temperature=0.0,
        max_tokens=None,
        format=None,
        request_timeout=None,
    ):  # noqa: ANN001
        blob = " ".join(m.content for m in messages)
        self.calls.append({"model": model, "content": blob})
        scores_json = [
            {
                "id": s.id,
                "relevance": s.relevance,
                "quality": s.quality,
                "timeliness": s.timeliness,
                "consistency": s.consistency,
            }
            for s in self.scores
        ]
        return json.dumps({"scores": scores_json})

    def ping(self):
        return {"ok": True}

    @property
    def default_model(self):
        return "fake"


def test_rank_spans_reorders_by_aggregate_score() -> None:
    spans = [
        EvidenceSpan(id="e1", text="weak text", url="http://a", title="A", verifiable=True),
        EvidenceSpan(id="e2", text="strong text", url="http://b", title="B", verifiable=True),
    ]
    # e2 scores higher on every dimension -> should come first.
    provider = _ScoringProvider(
        [
            SpanScore(id="e1", relevance=3, quality=3, timeliness=3, consistency=3),
            SpanScore(id="e2", relevance=9, quality=9, timeliness=9, consistency=9),
        ]
    )
    ranked = rank_spans(spans, "q", "title", "intent", provider, model="m")
    assert [s.id for s in ranked] == ["e2", "e1"]
    assert provider.calls[0]["model"] == "m"


def test_rank_spans_preserves_original_order_on_garbage_reply() -> None:
    spans = [
        EvidenceSpan(id="e1", text="a", url="http://a", title="A", verifiable=True),
        EvidenceSpan(id="e2", text="b", url="http://b", title="B", verifiable=True),
    ]

    class _GarbageProvider:
        name = "fake"

        def complete(
            self,
            messages,
            model=None,
            temperature=0.0,
            max_tokens=None,
            format=None,
            request_timeout=None,
        ):  # noqa: ANN001
            return "not json"

        def ping(self):
            return {"ok": True}

        @property
        def default_model(self):
            return "fake"

    ranked = rank_spans(spans, "q", "title", "intent", _GarbageProvider())
    assert [s.id for s in ranked] == ["e1", "e2"]


def test_rank_spans_preserves_original_order_on_provider_exception() -> None:
    spans = [
        EvidenceSpan(id="e1", text="a", url="http://a", title="A", verifiable=True),
        EvidenceSpan(id="e2", text="b", url="http://b", title="B", verifiable=True),
    ]

    class _ExplodingProvider:
        name = "fake"

        def complete(
            self,
            messages,
            model=None,
            temperature=0.0,
            max_tokens=None,
            format=None,
            request_timeout=None,
        ):  # noqa: ANN001
            raise RuntimeError("boom")

        def ping(self):
            return {"ok": True}

        @property
        def default_model(self):
            return "fake"

    ranked = rank_spans(spans, "q", "title", "intent", _ExplodingProvider())
    assert [s.id for s in ranked] == ["e1", "e2"]


def test_rank_spans_caps_at_max_spans() -> None:
    spans = [
        EvidenceSpan(id=f"e{i}", text=f"text {i}", url=f"http://{i}", title="T", verifiable=True)
        for i in range(5)
    ]
    # Score e4 highest but max_spans=3 -> e4 stays in tail.
    provider = _ScoringProvider(
        [
            SpanScore(id="e0", relevance=1, quality=1, timeliness=1, consistency=1),
            SpanScore(id="e1", relevance=2, quality=2, timeliness=2, consistency=2),
            SpanScore(id="e2", relevance=3, quality=3, timeliness=3, consistency=3),
        ]
    )
    ranked = rank_spans(spans, "q", "title", "intent", provider, model="m", max_spans=3)
    head = ranked[:3]
    tail = ranked[3:]
    assert [s.id for s in head] == ["e2", "e1", "e0"]
    assert [s.id for s in tail] == ["e3", "e4"]


def test_rank_spans_skips_unknown_ids_and_missing_scores() -> None:
    spans = [
        EvidenceSpan(id="e1", text="a", url="http://a", title="A", verifiable=True),
        EvidenceSpan(id="e2", text="b", url="http://b", title="B", verifiable=True),
        EvidenceSpan(id="e3", text="c", url="http://c", title="C", verifiable=True),
    ]
    # Reply omits e2 and contains unknown e99; e3 should win, e1 second, e2 keeps original index.
    provider = _ScoringProvider(
        [
            SpanScore(id="e3", relevance=9, quality=9, timeliness=9, consistency=9),
            SpanScore(id="e1", relevance=5, quality=5, timeliness=5, consistency=5),
            SpanScore(id="e99", relevance=10, quality=10, timeliness=10, consistency=10),
        ]
    )
    ranked = rank_spans(spans, "q", "title", "intent", provider)
    assert [s.id for s in ranked] == ["e3", "e1", "e2"]


def test_rank_spans_empty_returns_empty() -> None:
    provider = _ScoringProvider([])
    assert rank_spans([], "q", "title", "intent", provider) == []
