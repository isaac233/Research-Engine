"""Unit tests for the GPU/model residency probe."""

from __future__ import annotations

from typing import Any

import pytest

from research_engine.monitoring.gpu_probe import GpuProbe, LoadedModel


class FakePs:
    def __init__(self, entries: list[dict[str, Any]]) -> None:
        self._entries = entries

    def ps(self) -> list[dict[str, Any]]:
        return self._entries


def test_offload_pct_math() -> None:
    assert LoadedModel("m", 1000.0, 600.0).offload_pct == 0.4
    assert LoadedModel("m", 1000.0, 1000.0).offload_pct == 0.0  # fully on GPU
    assert LoadedModel("m", 0.0, 0.0).offload_pct == 0.0  # no divide by zero


def test_snapshot_none_when_no_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GpuProbe, "_nvidia_smi", staticmethod(lambda: None))
    assert GpuProbe().snapshot() is None


def test_snapshot_parses_models(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GpuProbe, "_nvidia_smi", staticmethod(lambda: (2000.0, 16000.0)))
    probe = GpuProbe(
        ollama_client=FakePs(
            [{"name": "gemma4:12b", "size": 8_000_000_000, "size_vram": 8_000_000_000}]
        )
    )
    snap = probe.snapshot()
    assert snap is not None
    assert snap.vram_total_mb == 16000.0
    assert snap.loaded_models[0].name == "gemma4:12b"
    assert snap.loaded_models[0].offload_pct == 0.0
    assert snap.as_dict()["models"][0]["size_vram_mb"] == 8000.0


def test_loaded_models_empty_without_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(GpuProbe, "_nvidia_smi", staticmethod(lambda: (100.0, 16000.0)))
    snap = GpuProbe().snapshot()
    assert snap is not None
    assert snap.loaded_models == []
