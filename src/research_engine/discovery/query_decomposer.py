"""LLM query decomposition — the evidence-volume lever.

WebWeaver issues ~18 search queries per task and banks ~100 pages; our heuristic
planner emits ~2 and banks ~3. RACE comprehensiveness/depth and FACT abundance all
scale with evidence volume. This turns one research question into several distinct
facet sub-queries so the web lane surfaces far more relevant candidates. Degrades
to the original query when no LLM is available or the reply can't be parsed — never
returns nothing.
"""

from __future__ import annotations

import json
import re
from typing import Any

from research_engine.llm.provider import LLMProvider, Message

_SYSTEM = "You decompose research questions into web search queries. Output ONLY JSON."
_USER = (
    "Research question: {query}\n\n"
    "List {n} DISTINCT web search queries that together cover the different facets, "
    "sub-topics, entities, time periods, and angles needed to answer it "
    "comprehensively. Each should be a concise search-engine query (not a sentence). "
    'JSON: {{"queries": ["...", "..."]}}'
)


def decompose_query(
    query: str,
    provider: LLMProvider | None,
    model: str | None = None,
    *,
    n: int = 8,
) -> list[str]:
    """Return up to ``n`` distinct facet sub-queries for ``query`` (original as fallback)."""
    if provider is None or not query.strip():
        return [query]
    messages = [
        Message(role="system", content=_SYSTEM),
        Message(role="user", content=_USER.format(query=query, n=n)),
    ]
    try:
        reply = provider.complete(messages, model=model, temperature=0.0, max_tokens=500)
        raw = _parse_json(reply).get("queries") or []
    except Exception:  # noqa: BLE001 — decomposition is best-effort; fall back
        return [query]
    subs: list[str] = []
    seen: set[str] = set()
    for item in raw:
        q = str(item).strip()
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            subs.append(q)
        if len(subs) >= n:
            break
    return subs or [query]


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
