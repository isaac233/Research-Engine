"""Ephemeral gap rubric (R3, DuMate arXiv:2606.07299 ρ^e).

DuMate refreshes an EPHEMERAL rubric each research cycle from the accumulated evidence:
it names the few most decision-relevant gaps still open (→ targeted gap queries) and
signals when no gap remains (→ adaptive stop). This is the evidence-CONDITIONED form of
the coverage ledger (which used a static entity×sub-question term-overlap grid and went
net-negative when it diluted retrieval): here the gaps come from a model reading what has
actually been banked against the question, bounded to ``max_queries`` per round, so it
ADDS depth instead of chasing a blind grid. Co-ReAct's warning (arXiv:2605.23590) is
respected — the rubric is injected only as concrete next queries, never as a numeric score.

It duck-types the ReactPlanner coverage-ledger slot (``ingest`` / ``gap_queries`` /
``is_complete``), so it drops in with no new planner param. One JSON-constrained LLM call
per ``ingest``; any failure degrades to "no gaps, not complete" → the loop behaves exactly
as if no ledger were set.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from research_engine.llm.provider import LLMProvider, Message
from research_engine.planning.summary_feedback import _reasoning_timeout

if TYPE_CHECKING:
    from research_engine.memory.evidence_bank import EvidenceBank

_EVIDENCE_MAX_CHARS = 3000
_SPAN_MAX_CHARS = 300

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "gaps": {"type": "array", "items": {"type": "string"}},
        "complete": {"type": "boolean"},
    },
    "required": ["gaps", "complete"],
}

_SYSTEM = (
    "You audit a research report's evidence coverage against its question and name what is "
    "still missing. Output ONLY JSON."
)
_USER = (
    "Research question: {query}\n\n"
    "Evidence gathered so far (verbatim spans):\n{evidence}\n\n"
    "Identify the MOST decision-relevant gaps still open for a complete answer. Return up to "
    "{k} concrete search queries that would fill them — each a specific, searchable phrase "
    "(named entity + aspect), NOT an instruction. If the evidence already covers the question "
    "with no material gap, return an empty list and complete=true.\n"
    'JSON: {{"gaps": ["..."], "complete": false}}'
)

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _parse_json(text: str) -> dict[str, Any]:
    match = _FENCE.search(text)
    candidate = match.group(1) if match else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start != -1 and end > start:
        candidate = candidate[start : end + 1]
    parsed = json.loads(candidate)
    if not isinstance(parsed, dict):
        raise ValueError("gap-rubric JSON is not an object")
    return parsed


class EphemeralGapRubric:
    """LLM gap rubric refreshed from the bank each round; duck-types the ledger slot."""

    def __init__(
        self,
        query: str,
        provider: LLMProvider,
        model: str | None = None,
        *,
        max_queries: int = 2,
    ) -> None:
        self.query = query
        self.provider = provider
        self.model = model
        self.max_queries = max(1, max_queries)
        self._gaps: tuple[str, ...] = ()
        self._complete = False

    def _digest(self, bank: EvidenceBank) -> str:
        parts: list[str] = []
        total = 0
        for span in bank.spans():
            text = span.text.strip()[:_SPAN_MAX_CHARS]
            if not text:
                continue
            parts.append(f"- {text}")
            total += len(text)
            if total >= _EVIDENCE_MAX_CHARS:
                break
        return "\n".join(parts)

    def ingest(self, bank: EvidenceBank) -> None:
        """One LLM call → cache this round's gap queries + completeness verdict.

        Recomputed each round (the bank is cumulative). Degrades to no-gaps/not-complete
        on any failure so a fault never aborts the plan or forces a premature stop.
        """
        messages = [
            Message(role="system", content=_SYSTEM),
            Message(
                role="user",
                content=_USER.format(
                    query=self.query, evidence=self._digest(bank), k=self.max_queries
                ),
            ),
        ]
        try:
            reply = self.provider.complete(
                messages,
                model=self.model,
                temperature=0.0,
                max_tokens=400,
                format=_SCHEMA,
                request_timeout=_reasoning_timeout(),
            )
            data = _parse_json(reply)
        except Exception:  # noqa: BLE001 — no rubric → loop continues as if no ledger, never fatal
            self._gaps, self._complete = (), False
            return
        gaps = tuple(s for x in (data.get("gaps") or []) if (s := str(x).strip()))
        self._gaps = gaps[: self.max_queries]
        self._complete = bool(data.get("complete")) and not self._gaps

    def gap_queries(self, max_queries: int) -> list[str]:
        """This round's gap queries, capped by both the caller's limit and ``max_queries``."""
        if max_queries <= 0:
            return []
        return list(self._gaps[: min(max_queries, self.max_queries)])

    def is_complete(self) -> bool:
        """True when the last ingest reported no outstanding gap (the adaptive-stop signal)."""
        return self._complete
