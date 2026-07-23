"""Unit tests for V3b comparison-table generation (grounded, FACT-safe)."""

from __future__ import annotations

import json
from typing import Any

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.synthesis.comparison_table import build_comparison_tables


class _FakeProvider:
    """Returns a canned reply (or raises) regardless of the prompt."""

    def __init__(self, reply: str | None = None, boom: bool = False) -> None:
        self._reply = reply or ""
        self._boom = boom

    def complete(self, messages: Any, model: Any = None, **_: Any) -> str:
        if self._boom:
            raise RuntimeError("provider down")
        return self._reply


def _bank(n: int = 4) -> EvidenceBank:
    srcs = [
        {
            "title": "T",
            "paper": {"url": f"https://a.org/{i}", "title": "T"},
            "claims": [{"claim": "c", "evidence": f"Fund {i} holds {i * 100} billion in assets."}],
        }
        for i in range(1, n + 1)
    ]
    return EvidenceBank.from_sources(srcs)


def _reply(rows: list[dict], columns: list[str] | None = None, title: str = "Funds") -> str:
    return json.dumps(
        {"title": title, "columns": columns if columns is not None else ["AUM", "Founded"], "rows": rows}
    )


def test_builds_table_from_valid_json() -> None:
    bank = _bank(3)
    ids = [s.id for s in bank.spans()]  # e1..e3
    rows = [
        {"entity": "Fund A", "cells": [
            {"column": "AUM", "value": "$100B", "span_id": ids[0]},
            {"column": "Founded", "value": "1990", "span_id": ids[1]},
        ]},
        {"entity": "Fund B", "cells": [
            {"column": "AUM", "value": "$200B", "span_id": ids[2]},
        ]},
    ]
    table = build_comparison_tables(bank, "compare funds", _FakeProvider(_reply(rows)))
    assert table.startswith("\n\n## Funds")
    assert "| Entity | AUM | Founded |" in table
    assert f"$100B [{ids[0]}]" in table
    assert "Fund B" in table


def test_cells_cite_real_span_ids_only() -> None:
    bank = _bank(2)
    ids = [s.id for s in bank.spans()]
    rows = [
        {"entity": "Fund A", "cells": [
            {"column": "AUM", "value": "$100B", "span_id": ids[0]},
            {"column": "Founded", "value": "1990", "span_id": "e999"},  # foreign id → dropped
        ]},
        {"entity": "Fund B", "cells": [
            {"column": "AUM", "value": "$200B", "span_id": ids[1]},
        ]},
    ]
    table = build_comparison_tables(bank, "q", _FakeProvider(_reply(rows)))
    assert "e999" not in table  # invented id never rendered
    assert "1990" not in table  # its value dropped with the foreign id
    assert f"$100B [{ids[0]}]" in table


def test_no_table_when_too_few_rows() -> None:
    bank = _bank(2)
    ids = [s.id for s in bank.spans()]
    rows = [{"entity": "Fund A", "cells": [{"column": "AUM", "value": "$100B", "span_id": ids[0]}]}]
    assert build_comparison_tables(bank, "q", _FakeProvider(_reply(rows))) == ""


def test_no_table_when_too_few_columns() -> None:
    bank = _bank(3)
    ids = [s.id for s in bank.spans()]
    rows = [
        {"entity": "A", "cells": [{"column": "AUM", "value": "1", "span_id": ids[0]}]},
        {"entity": "B", "cells": [{"column": "AUM", "value": "2", "span_id": ids[1]}]},
    ]
    assert build_comparison_tables(bank, "q", _FakeProvider(_reply(rows, columns=["AUM"]))) == ""


def test_degrades_on_provider_failure() -> None:
    assert build_comparison_tables(_bank(3), "q", _FakeProvider(boom=True)) == ""


def test_degrades_on_garbage_json() -> None:
    assert build_comparison_tables(_bank(3), "q", _FakeProvider("not json at all")) == ""


def test_empty_bank_returns_empty() -> None:
    assert build_comparison_tables(EvidenceBank([]), "q", _FakeProvider(_reply([]))) == ""
