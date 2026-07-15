"""Bounded parallel map — overlap I/O-bound work while preserving order.

The screening/extraction pipeline fetches a page and runs a local LLM per source,
sequentially — ~30 min/task, which caps how much evidence we can bank (the proven
lever). Overlapping the per-source fetch (network) across a small worker pool cuts
wall-clock materially even though Ollama serialises GPU inference (the fetch waits
overlap, and Ollama pipelines/continuous-batches queued requests). Results stay in
input order and a single failing item yields ``None`` instead of aborting the batch,
so callers keep the successful results and skip the failures.

Only pure work (fetch + LLM, no shared store/event state) should be mapped here —
keep SQLite writes and event emission on the calling thread.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_DEFAULT_WORKERS = 4


def max_workers_from_env(default: int = _DEFAULT_WORKERS) -> int:
    """Read ``RESEARCH_ENGINE_MAX_WORKERS`` (>=1), falling back to ``default``."""
    raw = os.environ.get("RESEARCH_ENGINE_MAX_WORKERS")
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def parallel_map[T, R](
    func: Callable[[T], R],
    items: Sequence[T],
    *,
    max_workers: int = _DEFAULT_WORKERS,
) -> list[R | None]:
    """Apply ``func`` to each item across a bounded pool; ordered, per-item errors → ``None``."""
    if not items:
        return []

    def _safe(item: T) -> R | None:
        try:
            return func(item)
        except Exception:  # noqa: BLE001 — isolate one item's failure from the batch
            logger.warning("parallel_map item failed", exc_info=True)
            return None

    workers = min(max(1, max_workers), len(items))
    if workers == 1:
        return [_safe(it) for it in items]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_safe, items))
