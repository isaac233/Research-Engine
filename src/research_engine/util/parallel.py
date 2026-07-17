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
from concurrent.futures import TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

_DEFAULT_WORKERS = 4
# A single fetch + LLM extract completes in seconds; anything past this is a wedged
# Ollama/httpx call that would otherwise hang the whole batch (a stuck extract worker
# froze a campaign for >100 min). Bounded so one bad item yields None, not a freeze.
_DEFAULT_ITEM_TIMEOUT = 180.0


def max_workers_from_env(default: int = _DEFAULT_WORKERS) -> int:
    """Read ``RESEARCH_ENGINE_MAX_WORKERS`` (>=1), falling back to ``default``."""
    raw = os.environ.get("RESEARCH_ENGINE_MAX_WORKERS")
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def item_timeout_from_env(default: float | None = _DEFAULT_ITEM_TIMEOUT) -> float | None:
    """Read ``RESEARCH_ENGINE_ITEM_TIMEOUT`` seconds; ``<=0`` disables the timeout."""
    raw = os.environ.get("RESEARCH_ENGINE_ITEM_TIMEOUT")
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else None


def parallel_map[T, R](
    func: Callable[[T], R],
    items: Sequence[T],
    *,
    max_workers: int = _DEFAULT_WORKERS,
    item_timeout: float | None = None,
) -> list[R | None]:
    """Apply ``func`` to each item across a bounded pool; ordered, per-item errors → ``None``.

    ``item_timeout`` (seconds) bounds each item: a worker still running past it yields
    ``None`` and the batch continues. This only preempts I/O-bound work (a stuck httpx
    call releases the GIL); a CPU-bound hang holds the GIL and cannot be interrupted here.
    The abandoned worker unwinds on its own (e.g. the httpx timeout) — we don't wait on it.
    """
    if not items:
        return []

    def _safe(item: T) -> R | None:
        try:
            return func(item)
        except Exception:  # noqa: BLE001 — isolate one item's failure from the batch
            logger.warning("parallel_map item failed", exc_info=True)
            return None

    workers = min(max(1, max_workers), len(items))
    # A serial call cannot be timed out (nothing else runs to abandon it), so the
    # fast path only applies when no timeout is asked for.
    if workers == 1 and item_timeout is None:
        return [_safe(it) for it in items]

    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        futures = [pool.submit(_safe, it) for it in items]
        results: list[R | None] = []
        for future in futures:
            try:
                results.append(future.result(timeout=item_timeout))
            except FuturesTimeoutError:
                logger.warning("parallel_map item timed out after %ss", item_timeout)
                future.cancel()
                results.append(None)
        return results
    finally:
        # Never block batch return on a hung I/O worker; it unwinds at its own
        # timeout. cancel_futures drops anything not yet started.
        pool.shutdown(wait=False, cancel_futures=True)
