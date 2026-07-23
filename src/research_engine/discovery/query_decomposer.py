"""Objective-driven query decomposition — the evidence-volume + coverage lever.

WebWeaver issues ~18 search queries per task and banks ~100 pages; our heuristic
planner emits ~2 and banks ~3. RACE comprehensiveness/depth and FACT abundance all
scale with evidence volume — AND with how completely the queries cover what the
report must answer. "Don't Stop Early" (arXiv:2604.24978) shows building the
information objectives from the TASK *before* retrieval beats inducing structure
from whatever happened to be fetched (early retrieval biases toward tangential,
easily-accessible details). So this first enumerates the sub-questions a complete
answer must cover, then emits one search query per objective. Degrades to the
original query when no LLM is available or the reply can't be parsed.
"""

from __future__ import annotations

import json
import re
from typing import Any

from research_engine.llm.provider import LLMProvider, Message

_SYSTEM = "You plan research coverage as information objectives + search queries. Output ONLY JSON."
# Grammar-constrained decoding schema (Ollama `format`): forces valid JSON so a
# capable local model returns the full plan instead of degrading to the
# single-query fallback on a parse miss — protecting the evidence-volume lever.
_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "objectives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string"},
                    "query": {"type": "string"},
                },
                "required": ["objective", "query"],
            },
        }
    },
    "required": ["objectives"],
}
_USER = (
    "Research question: {query}\n\n"
    "First identify the INFORMATION OBJECTIVES a complete report must cover — the "
    "distinct sub-questions, entities, time periods, comparisons, mechanisms, and "
    "angles the answer needs. Then, for EACH objective, write one concise web search "
    "query (not a sentence) that would surface evidence for it. Aim for {n} "
    "objectives that together cover the question comprehensively.\n"
    'JSON: {{"objectives": [{{"objective": "<sub-question>", "query": "<search query>"}}]}}'
)


def _plan(
    query: str, provider: LLMProvider | None, model: str | None, n: int
) -> list[tuple[str, str]]:
    """Return up to ``n`` (objective, query) pairs; empty on any failure."""
    if provider is None or not query.strip():
        return []
    messages = [
        Message(role="system", content=_SYSTEM),
        Message(role="user", content=_USER.format(query=query, n=n)),
    ]
    try:
        reply = provider.complete(
            messages, model=model, temperature=0.0, max_tokens=700, format=_SCHEMA
        )
        parsed = _parse_json(reply)
    except Exception:  # noqa: BLE001 — planning is best-effort; caller falls back
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for item in _iter_items(parsed):
        obj = str(item.get("objective", "")).strip()
        q = str(item.get("query", "") or obj).strip()
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            pairs.append((obj or q, q))
        if len(pairs) >= n:
            break
    return pairs


def _iter_items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept the objectives shape; tolerate a bare ``queries`` list for robustness."""
    objectives = parsed.get("objectives")
    if isinstance(objectives, list):
        return [o if isinstance(o, dict) else {"query": str(o)} for o in objectives]
    queries = parsed.get("queries")
    if isinstance(queries, list):
        return [{"query": str(q)} for q in queries]
    return []


def decompose_query(
    query: str,
    provider: LLMProvider | None,
    model: str | None = None,
    *,
    n: int = 8,
) -> list[str]:
    """Return up to ``n`` objective-covering search queries (original as fallback)."""
    pairs = _plan(query, provider, model, n)
    return [q for _obj, q in pairs] or [query]


def plan_objectives(
    query: str,
    provider: LLMProvider | None,
    model: str | None = None,
    *,
    n: int = 8,
) -> list[str]:
    """Return the report's information objectives (sub-questions) for ``query``."""
    return [obj for obj, _q in _plan(query, provider, model, n)]


_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    match = _FENCE.search(text)
    candidate = match.group(1) if match else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("decomposition JSON is not an object")
    return parsed
