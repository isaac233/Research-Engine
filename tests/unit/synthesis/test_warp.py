"""WARP draft<->deepen loop (R4, finish_line_execution_v9).

warp_deepen iterates the existing single-pass deepen_report: re-diagnose the updated
draft each round, stop on convergence (a round changes nothing) or the round cap. These
tests isolate the LOOP by stubbing deepen_report — the single-pass mechanics are covered
in test_deepen.
"""

from __future__ import annotations

import research_engine.synthesis.deepen as d


def test_warp_stops_on_convergence(monkeypatch) -> None:  # noqa: ANN001
    calls = {"n": 0}

    def fake_deepen(draft, bank, query, provider, model=None, *, max_expand=2):  # noqa: ANN001, ANN003
        calls["n"] += 1
        return draft  # no change → converged

    monkeypatch.setattr(d, "deepen_report", fake_deepen)
    out = d.warp_deepen("draft", bank=None, query="q", provider=None, rounds=5)
    assert out == "draft"
    assert calls["n"] == 1  # stopped after the first no-change round, not all 5


def test_warp_iterates_until_round_cap(monkeypatch) -> None:  # noqa: ANN001
    calls = {"n": 0}

    def fake_deepen(draft, bank, query, provider, model=None, *, max_expand=2):  # noqa: ANN001, ANN003
        calls["n"] += 1
        return f"{draft} r{calls['n']}"  # always changes

    monkeypatch.setattr(d, "deepen_report", fake_deepen)
    out = d.warp_deepen("draft", bank=None, query="q", provider=None, rounds=3)
    assert calls["n"] == 3  # ran the full cap
    assert out == "draft r1 r2 r3"


def test_warp_single_round_is_one_deepen(monkeypatch) -> None:  # noqa: ANN001
    calls = {"n": 0}

    def fake_deepen(draft, bank, query, provider, model=None, *, max_expand=2):  # noqa: ANN001, ANN003
        calls["n"] += 1
        return f"{draft} x"

    monkeypatch.setattr(d, "deepen_report", fake_deepen)
    d.warp_deepen("draft", bank=None, query="q", provider=None, rounds=1)
    assert calls["n"] == 1  # rounds=1 == today's single deepen pass


def test_warp_rounds_floor_is_one(monkeypatch) -> None:  # noqa: ANN001
    calls = {"n": 0}

    def fake_deepen(draft, bank, query, provider, model=None, *, max_expand=2):  # noqa: ANN001, ANN003
        calls["n"] += 1
        return f"{draft} x"

    monkeypatch.setattr(d, "deepen_report", fake_deepen)
    d.warp_deepen("draft", bank=None, query="q", provider=None, rounds=0)
    assert calls["n"] == 1  # rounds<1 clamps to one pass
