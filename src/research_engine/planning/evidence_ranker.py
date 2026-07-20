"""Evidence-ranking critic (R6, RhinoInsight arXiv:2511.18743 evidence-audit).

Before the writer sees a section's spans, score each span on relevance, source
quality, timeliness, and consistency with the other spans. Reorder the section's
evidence IDs so the writer consumes the strongest evidence first. On any failure
the original order is preserved.

NOTE: we intentionally SKIP RhinoInsight's cluster-summary step. Summarising spans
before citing reintroduces the hallucination surface that ``EvidenceBank`` was
designed to eliminate; this module only scores and reorders verbatim spans.
"""

from __future__ import annotations

import dataclasses
import json
import re
from collections.abc import Sequence
from typing import Any

from research_engine.llm.provider import LLMProvider, Message
from research_engine.memory.evidence_bank import EvidenceSpan

# Score weights (must sum to 1.0).
_RELEVANCE_WEIGHT = 0.40
_QUALITY_WEIGHT = 0.25
_TIMELINESS_WEIGHT = 0.20
_CONSISTENCY_WEIGHT = 0.15

# Cap spans per scoring call to keep the prompt inside a modest context window.
_DEFAULT_MAX_SPANS = 20
_SPAN_MAX_CHARS = 300

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scores": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "relevance": {"type": "integer"},
                    "quality": {"type": "integer"},
                    "timeliness": {"type": "integer"},
                    "consistency": {"type": "integer"},
                },
                "required": ["id", "relevance", "quality", "timeliness", "consistency"],
            },
        }
    },
    "required": ["scores"],
}

_SYSTEM = (
    "You audit evidence spans for one report section. Score each span independently "
    "on four 1-10 dimensions. Output ONLY JSON matching the requested schema. "
    "Do NOT summarise, cluster, or rewrite the spans."
)

_USER = (
    "Research question: {query}\n\n"
    "Section: {title}\nSection intent: {intent}\n\n"
    "Evidence spans (id: text):\n{evidence}\n\n"
    "Score each span from 1 (worst) to 10 (best) on:\n"
    "- relevance: how directly it addresses this section's intent.\n"
    "- quality: source authority, specificity, and factual concreteness.\n"
    "- timeliness: recency and currency for the question (10 = very recent/relevant).\n"
    "- consistency: coherence with the other spans (no contradiction, supports the same narrative).\n\n"
    'Return JSON: {{"scores": [{{"id": "e1", "relevance": 8, "quality": 7, "timeliness": 6, "consistency": 9}}, ...]}}'
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@dataclasses.dataclass(frozen=True, slots=True)
class SpanScore:
    """Four-dimensional score for one evidence span."""

    id: str
    relevance: int
    quality: int
    timeliness: int
    consistency: int

    @property
    def aggregate(self) -> float:
        """Weighted aggregate score for ranking."""
        return (
            self.relevance * _RELEVANCE_WEIGHT
            + self.quality * _QUALITY_WEIGHT
            + self.timeliness * _TIMELINESS_WEIGHT
            + self.consistency * _CONSISTENCY_WEIGHT
        )


def _parse_json(text: str) -> dict[str, Any]:
    """Extract the first JSON object from the reply."""
    match = _FENCE.search(text)
    candidate = match.group(1) if match else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("evidence-ranker JSON is not an object")
    return parsed


def _format_spans(spans: Sequence[EvidenceSpan]) -> str:
    """Build a compact, deterministic prompt block for the spans."""
    lines: list[str] = []
    for s in spans:
        text = s.text.strip()[:_SPAN_MAX_CHARS].replace("\n", " ")
        lines.append(f"[{s.id}] {text}")
    return "\n".join(lines)


def _normalize_score(value: Any) -> int:
    """Clamp an incoming score to 1-10; invalid values become 5."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 5
    return max(1, min(10, score))


def _parse_scores(reply: str, span_ids: set[str]) -> dict[str, SpanScore]:
    """Parse the LLM JSON reply into a map of span id -> SpanScore."""
    parsed = _parse_json(reply)
    raw_scores = parsed.get("scores") if isinstance(parsed, dict) else None
    scores: list[Any] = raw_scores if isinstance(raw_scores, list) else []
    result: dict[str, SpanScore] = {}
    for item in scores:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("id", ""))
        if sid not in span_ids:
            continue
        result[sid] = SpanScore(
            id=sid,
            relevance=_normalize_score(item.get("relevance")),
            quality=_normalize_score(item.get("quality")),
            timeliness=_normalize_score(item.get("timeliness")),
            consistency=_normalize_score(item.get("consistency")),
        )
    return result


def rank_spans(
    spans: Sequence[EvidenceSpan],
    query: str,
    section_title: str,
    section_intent: str,
    provider: LLMProvider,
    model: str | None = None,
    *,
    max_spans: int = _DEFAULT_MAX_SPANS,
) -> list[EvidenceSpan]:
    """Return ``spans`` reordered by the four-dimensional critic score.

    The original order is preserved when the LLM call fails, the reply is
    malformed, or no scores are returned. Only the first ``max_spans`` spans are
    scored; extras keep their original relative order at the tail.
    """
    if not spans:
        return []

    work = list(spans[:max_spans])
    tail = list(spans[max_spans:])
    span_ids = {s.id for s in work}
    original_index = {s.id: i for i, s in enumerate(work)}

    messages = [
        Message(role="system", content=_SYSTEM),
        Message(
            role="user",
            content=_USER.format(
                query=query,
                title=section_title,
                intent=section_intent,
                evidence=_format_spans(work),
            ),
        ),
    ]
    try:
        reply = provider.complete(
            messages,
            model=model,
            temperature=0.0,
            format=_SCHEMA,
        )
        scores = _parse_scores(reply, span_ids)
    except Exception:  # noqa: BLE001 — degrade to original order on any fault
        return list(spans)

    if not scores:
        return list(spans)

    def _key(span: EvidenceSpan) -> tuple[float, int]:
        score = scores.get(span.id)
        if score is None:
            return (-1.0, original_index[span.id])
        return (-score.aggregate, original_index[span.id])

    ranked = sorted(work, key=_key)
    return ranked + tail
