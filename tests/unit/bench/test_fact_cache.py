"""Tests for the FACT fetch record/replay cache."""
from __future__ import annotations

from pathlib import Path

import pytest

from bench.fact import _maybe_cache_fetcher
from bench.fact_cache import FactFetchCache


def test_cache_roundtrip(tmp_path: Path) -> None:
    cache = FactFetchCache(str(tmp_path / "c.db"))
    assert cache.get("http://x") is None
    cache.put("http://x", "hello")
    assert cache.get("http://x") == "hello"


def test_wrapper_is_noop_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RESEARCH_ENGINE_BENCH_FACT_CACHE", raising=False)
    calls: list[str] = []

    def base(url: str) -> str:
        calls.append(url)
        return "live"

    wrapped = _maybe_cache_fetcher(base)
    assert wrapped is base  # unset => base fetcher unchanged
    wrapped("http://x")
    wrapped("http://x")
    assert calls == ["http://x", "http://x"]  # fetched every time


def test_wrapper_replays_when_enabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("RESEARCH_ENGINE_BENCH_FACT_CACHE", "1")
    monkeypatch.setenv("RESEARCH_ENGINE_BENCH_FACT_CACHE_PATH", str(tmp_path / "c.db"))
    calls: list[str] = []

    def base(url: str) -> str:
        calls.append(url)
        return "PAGE"

    wrapped = _maybe_cache_fetcher(base)
    assert wrapped("http://x") == "PAGE"
    assert wrapped("http://x") == "PAGE"  # 2nd = replay
    assert calls == ["http://x"]  # fetched from live web only once


def test_wrapper_does_not_cache_failures(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RESEARCH_ENGINE_BENCH_FACT_CACHE", "1")
    monkeypatch.setenv("RESEARCH_ENGINE_BENCH_FACT_CACHE_PATH", str(tmp_path / "c.db"))
    calls: list[str] = []

    def base(url: str) -> str:
        calls.append(url)
        return "scrape failed: 403"

    wrapped = _maybe_cache_fetcher(base)
    wrapped("http://x")
    wrapped("http://x")
    assert calls == ["http://x", "http://x"]  # failures re-fetched, never cached
