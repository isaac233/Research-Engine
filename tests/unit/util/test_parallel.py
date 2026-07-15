"""Unit tests for the bounded parallel-map helper."""

from __future__ import annotations

from research_engine.util.parallel import parallel_map


def test_order_preserved() -> None:
    assert parallel_map(lambda x: x * 2, [1, 2, 3, 4], max_workers=3) == [2, 4, 6, 8]


def test_failing_item_isolated_to_none() -> None:
    def f(x: int) -> int:
        if x == 2:
            raise ValueError("boom")
        return x

    assert parallel_map(f, [1, 2, 3], max_workers=2) == [1, None, 3]


def test_empty_input() -> None:
    assert parallel_map(lambda x: x, [], max_workers=4) == []


def test_single_worker_runs_serially() -> None:
    assert parallel_map(lambda x: x + 1, [10, 20], max_workers=1) == [11, 21]
