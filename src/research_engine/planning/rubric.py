"""Persistent self-rubric (DuMate-style test-time scaffold, P1).

The DeepResearch Bench judge scores against a task-specific rubric it generates
from the prompt (criteria per dimension + weights). Leaderboard #1
DuMate-DeepResearch (arXiv:2606.07299) turns that around: generate a rubric
from the task prompt at inference time and inject it as a live scaffold —
sections shape the outline, guidance shapes planning and writing. No test-set
leakage: only the task prompt is used, mirroring the judge's own public
criteria-generation procedure (deep_research_bench prompt/criteria_prompt_en).

One JSON-constrained LLM call at campaign start; any failure degrades to a
trivial rubric (no sections, no guidance) → the default path is unchanged.
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
        "title": {"type": "string"},
        "scope": {"type": "string"},
        "sections": {"type": "array", "items": {"type": "string"}},
        "guidance": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["title", "scope", "sections", "guidance"],
}

_SYSTEM = (
    "You are an expert research editor. Given a research task, you design the rubric a "
    "strict evaluator would score the report against, then express it as a report plan. "
    "Output ONLY JSON."
)

# The recurring shape of the bench's own criteria across tasks: definition/scope
# first; entity breadth; quantitative depth; comparative synthesis; trends; risks/
# governance. Generic report craft, not any one task's answer key.
_USER = (
    "Research task: {query}\n\n"
    "Produce a JSON rubric-plan for a reference-grade research report:\n"
    '- "title": a compound analytical report title (noun phrase, not the task restated).\n'
    '- "scope": one sentence pinning the concrete scope and cohort you assume, resolving '
    "any ambiguity in the task.\n"
    '- "sections": 6-10 noun-phrase section titles a complete report needs, ordered: open '
    "with definition/scope of the subject, cover each major dimension the task implies, "
    "include one comparative-synthesis section and one trends/outlook section, close with "
    "risks or open questions. Each title must be a searchable topic, not an instruction.\n"
    '- "guidance": 5-8 short imperative quality criteria the writer must satisfy, e.g. '
    "define the cohort explicitly; give quantitative data (sizes, allocations, dates) in "
    "every section; compare entities rather than describing them in isolation; attribute "
    "claims to named primary sources; use precise domain terminology; state implications, "
    "not just facts.\n"
    'JSON: {{"title":"...","scope":"...","sections":["..."],"guidance":["..."]}}'
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


@dataclasses.dataclass(frozen=True, slots=True)
class Rubric:
    """Persistent task rubric: report shape + quality guidance."""

    title: str
    scope: str
    sections: tuple[str, ...]
    guidance: tuple[str, ...]

    def digest(self) -> str:
        """Compact prompt block for the planner/writer; "" when trivial."""
        if not self.guidance and not self.scope:
            return ""
        lines: list[str] = []
        if self.scope:
            lines.append(f"Scope: {self.scope}")
        if self.guidance:
            lines.append("Quality criteria:")
            lines.extend(f"- {g}" for g in self.guidance)
        return "\n".join(lines)


TRIVIAL = Rubric(title="", scope="", sections=(), guidance=())


def _parse_json(text: str) -> dict[str, Any]:
    match = _FENCE.search(text)
    candidate = match.group(1) if match else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("rubric JSON is not an object")
    return parsed


def build_rubric(query: str, provider: LLMProvider, model: str | None = None) -> Rubric:
    """One JSON-constrained LLM call → a persistent rubric; degrades to TRIVIAL."""
    messages = [
        Message(role="system", content=_SYSTEM),
        Message(role="user", content=_USER.format(query=query)),
    ]
    try:
        reply = provider.complete(
            messages, model=model, temperature=0.0, max_tokens=800, format=_SCHEMA
        )
        data = _parse_json(reply)
    except Exception:  # noqa: BLE001 — no rubric → default path, never fatal
        return TRIVIAL
    sections = tuple(s for x in (data.get("sections") or []) if (s := str(x).strip()))
    guidance = tuple(s for x in (data.get("guidance") or []) if (s := str(x).strip()))
    return Rubric(
        title=str(data.get("title") or "").strip(),
        scope=str(data.get("scope") or "").strip(),
        sections=sections[:10],
        guidance=guidance[:8],
    )
