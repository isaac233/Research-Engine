"""V10 lever V3b: comparison tables from numeric spans (DeepSurvey arXiv:2605.29522).

Before the abstain gate, build ONE markdown comparison table of the question's key
entities across their comparable quantitative dimensions. Every cell value comes
from a banked span and cites that span's id, so the table is FACT-safe by
construction (the parity judge checks each cite against its page; the abstain gate
downstream still vets them). Degrades to "" (no table) on any parse/provider fault
or when there is not enough comparable numeric evidence.

Env-gated in the orchestrator (``RESEARCH_ENGINE_COMPARISON_TABLES``); off ⇒ this
module is never called and the draft is unchanged.
"""

from __future__ import annotations

import json
import re
from typing import Any

from research_engine.llm.provider import LLMProvider, Message
from research_engine.memory.evidence_bank import EvidenceBank

_MAX_SPANS = 40
_SPAN_MAX_CHARS = 300
_MIN_ROWS = 2
_MIN_COLS = 2

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "columns": {"type": "array", "items": {"type": "string"}},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "entity": {"type": "string"},
                    "cells": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "value": {"type": "string"},
                                "span_id": {"type": "string"},
                            },
                            "required": ["column", "value", "span_id"],
                        },
                    },
                },
                "required": ["entity", "cells"],
            },
        },
    },
    "required": ["title", "columns", "rows"],
}

_SYSTEM = (
    "You build ONE markdown-ready comparison table from evidence spans for a research "
    "report. Compare the question's key entities across their comparable quantitative "
    "dimensions (amounts, dates, percentages, sizes). Every cell value MUST come from a "
    "span and cite that span's id. Invent no numbers; omit a cell if no span supports it. "
    "Output ONLY JSON matching the schema."
)

_USER = (
    "Research question: {query}\n\n"
    "Evidence spans (id: text):\n{evidence}\n\n"
    "Return a table: a short title, 2+ comparable dimension columns, and one row per "
    "entity. Each cell = {{column, value, span_id}} where span_id is the id the value "
    "comes from. Only include cells grounded in a span."
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
        raise ValueError("comparison-table JSON is not an object")
    return parsed


def _format_spans(bank: EvidenceBank) -> str:
    lines: list[str] = []
    for s in bank.spans()[:_MAX_SPANS]:
        text = s.text.strip()[:_SPAN_MAX_CHARS].replace("\n", " ")
        lines.append(f"[{s.id}] {text}")
    return "\n".join(lines)


def _cell(value: str, span_id: str, valid_ids: set[str]) -> str | None:
    """Render one cell ``value [span_id]`` only when the span id is real."""
    value = str(value).strip()
    span_id = str(span_id).strip()
    if not value or span_id not in valid_ids:
        return None
    return f"{value} [{span_id}]"


def build_comparison_tables(
    bank: EvidenceBank, query: str, provider: LLMProvider, model: str | None = None
) -> str:
    """Return a markdown ``## Comparison`` table block grounded in banked spans, or "".

    FACT-safe: every cell cites a real span id (foreign/invented ids are dropped);
    an under-populated table (< 2 rows or < 2 columns) yields "".
    """
    spans = bank.spans()
    if len(spans) < _MIN_ROWS:
        return ""
    valid_ids = {s.id for s in spans}
    messages = [
        Message(role="system", content=_SYSTEM),
        Message(role="user", content=_USER.format(query=query, evidence=_format_spans(bank))),
    ]
    try:
        reply = provider.complete(messages, model=model, temperature=0.0, format=_SCHEMA)
        parsed = _parse_json(reply)
    except Exception:  # noqa: BLE001 — no table on any fault, draft proceeds unchanged
        return ""

    title = str(parsed.get("title") or "Comparison").strip()
    columns = [str(c).strip() for c in (parsed.get("columns") or []) if str(c).strip()]
    rows_in = parsed.get("rows") or []
    if len(columns) < _MIN_COLS or not isinstance(rows_in, list):
        return ""

    body: list[str] = []
    for row in rows_in:
        if not isinstance(row, dict):
            continue
        entity = str(row.get("entity") or "").strip()
        by_col = {str(c.get("column", "")).strip(): c for c in (row.get("cells") or []) if isinstance(c, dict)}
        if not entity or not by_col:
            continue
        cells = [entity]
        grounded = False
        for col in columns:
            spec = by_col.get(col)
            rendered = _cell(spec.get("value", ""), spec.get("span_id", ""), valid_ids) if spec else None
            if rendered:
                grounded = True
            cells.append(rendered or "—")
        if grounded:
            body.append("| " + " | ".join(cells) + " |")

    if len(body) < _MIN_ROWS:
        return ""
    header = "| " + " | ".join(["Entity", *columns]) + " |"
    divider = "| " + " | ".join(["---"] * (len(columns) + 1)) + " |"
    return f"\n\n## {title}\n\n{header}\n{divider}\n" + "\n".join(body) + "\n"
