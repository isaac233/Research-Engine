"""Unit tests for the bounded parallel-map helper."""

from __future__ import annotations

import time

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


def test_slow_item_times_out_to_none() -> None:
    # A hung item (here a sleep; in production a wedged Ollama/httpx call) must not
    # block the whole batch — it yields None after item_timeout while the rest return.
    # Regression: an extract worker stuck in httpx froze the campaign for >100 min.
    def f(x: int) -> int:
        if x == 2:
            time.sleep(5)
        return x

    start = time.monotonic()
    out = parallel_map(f, [1, 2, 3], max_workers=3, item_timeout=0.5)
    elapsed = time.monotonic() - start
    assert out == [1, None, 3]
    assert elapsed < 3.0, f"batch waited {elapsed:.1f}s — timeout did not release it"
