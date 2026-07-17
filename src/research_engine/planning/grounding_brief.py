"""Autonomous grounding brief (ADORE, W4): scope a vague query BEFORE retrieval.

A broad/underspecified query ("how the world's wealthiest governments invest") never gets
scoped into concrete, fetchable, verifiable sub-targets, so retrieval drifts and the report
misses dimensions (task 53). ADORE's Grounding Agent (arXiv:2601.18267, RACE 52.65) fixes
this with ONE pre-search LLM call that proposes explicit scope assumptions autonomously (no
user clarification — correct for an offline benchmark): a concrete brief of scope,
definitions, the entities the query implies, and per-section success criteria.

Here the brief's ``entities`` × ``section_criteria`` seed the coverage ledger (W2) so its
gap queries are concrete ("Norway GPFG asset allocation"). Any failure degrades to a
trivial brief (scope = the raw query, no entities) → the ledger stays a no-op → the default
path is unchanged.
"""

from __future__ import annotations

import dataclasses
import json
import re
from typing import Any

from research_engine.llm.provider import LLMProvider, Message

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scope": {"type": "string"},
        "definitions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"term": {"type": "string"}, "definition": {"type": "string"}},
                "required": ["term", "definition"],
            },
        },
        "entities": {"type": "array", "items": {"type": "string"}},
        "section_criteria": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["scope", "entities", "section_criteria"],
}

_SYSTEM = (
    "You scope an underspecified research question into a concrete brief BEFORE any search. "
    "Make reasonable scope assumptions yourself; do not ask the user anything. Output ONLY JSON."
)
_USER = (
    "Research question: {query}\n\n"
    "Produce a JSON brief:\n"
    '- "scope": one sentence stating the concrete scope you are assuming.\n'
    '- "definitions": key terms that need pinning down, each {{"term","definition"}}.\n'
    '- "entities": the specific named entities this question implies (concrete instances of '
    'any general class in it), e.g. named organizations, funds, countries, or products.\n'
    '- "section_criteria": the cross-cutting sub-questions a complete report must answer '
    "for each entity (the report's dimensions).\n"
    'JSON: {{"scope":"...","definitions":[],"entities":["..."],"section_criteria":["..."]}}'
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@dataclasses.dataclass(frozen=True, slots=True)
class GroundingBrief:
    """Autonomously-scoped brief for a vague query."""

    scope: str
    definitions: dict[str, str]
    entities: tuple[str, ...]
    section_criteria: tuple[str, ...]


def _parse_json(text: str) -> dict[str, Any]:
    match = _FENCE.search(text)
    candidate = match.group(1) if match else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("brief JSON is not an object")
    return parsed


def build_grounding_brief(
    query: str, provider: LLMProvider, model: str | None = None
) -> GroundingBrief:
    """One JSON-constrained LLM call → a concrete brief; degrades to the raw query."""
    trivial = GroundingBrief(scope=query, definitions={}, entities=(), section_criteria=())
    messages = [
        Message(role="system", content=_SYSTEM),
        Message(role="user", content=_USER.format(query=query)),
    ]
    try:
        reply = provider.complete(
            messages, model=model, temperature=0.0, max_tokens=600, format=_SCHEMA
        )
        data = _parse_json(reply)
    except Exception:  # noqa: BLE001 — no brief → trivial scope, never fatal
        return trivial

    scope = str(data.get("scope") or query).strip() or query
    definitions: dict[str, str] = {}
    for item in data.get("definitions") or []:
        if isinstance(item, dict) and str(item.get("term", "")).strip():
            definitions[str(item["term"]).strip()] = str(item.get("definition", "")).strip()
    entities = tuple(
        s for e in (data.get("entities") or []) if (s := str(e).strip())
    )
    criteria = tuple(
        s for c in (data.get("section_criteria") or []) if (s := str(c).strip())
    )
    return GroundingBrief(
        scope=scope, definitions=definitions, entities=entities, section_criteria=criteria
    )
