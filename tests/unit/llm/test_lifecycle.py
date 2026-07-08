"""Unit tests for the model lifecycle manager."""

from __future__ import annotations

from typing import Any

import pytest

from research_engine.llm.lifecycle import ModelLifecycleManager


class FakeClient:
    """Records warm/unload/ps calls; ps reflects the loaded set."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self._loaded: set[str] = set()

    def warm(self, model: str, keep_alive: Any = "5m", options: Any = None) -> bool:
        self.calls.append(("warm", model))
        self._loaded.add(model)
        return True

    def unload(self, model: str) -> bool:
        self.calls.append(("unload", model))
        self._loaded.discard(model)
        return True

    def ps(self) -> list[dict[str, Any]]:
        return [{"name": m} for m in sorted(self._loaded)]


def test_load_sets_current_and_active() -> None:
    client = FakeClient()
    mgr = ModelLifecycleManager(client)
    assert mgr.load("gemma4:12b") is True
    assert mgr.current == "gemma4:12b"
    assert mgr.active() == ["gemma4:12b"]


def test_switch_unloads_previous_then_loads_new() -> None:
    client = FakeClient()
    mgr = ModelLifecycleManager(client)
    mgr.load("a")
    mgr.switch("b")
    assert ("unload", "a") in client.calls
    assert ("warm", "b") in client.calls
    assert mgr.active() == ["b"]  # only one model resident


def test_switch_same_model_is_noop_reload() -> None:
    client = FakeClient()
    mgr = ModelLifecycleManager(client)
    mgr.load("a")
    client.calls.clear()
    mgr.switch("a")
    assert ("unload", "a") not in client.calls


def test_with_model_evicts_on_exit() -> None:
    client = FakeClient()
    mgr = ModelLifecycleManager(client)
    with mgr.with_model("x"):
        assert mgr.active() == ["x"]
    assert mgr.active() == []
    assert mgr.current is None


def test_with_model_evicts_on_exception() -> None:
    client = FakeClient()
    mgr = ModelLifecycleManager(client)
    with pytest.raises(RuntimeError), mgr.with_model("x"):
        raise RuntimeError("boom")
    assert mgr.active() == []  # evicted despite the error


def test_event_hook_receives_switch() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    mgr = ModelLifecycleManager(FakeClient(), on_event=lambda e, p: events.append((e, p)))
    mgr.load("a")
    mgr.switch("b")
    kinds = [e for e, _ in events]
    assert "model_load" in kinds
    assert "model_switch" in kinds
    assert "model_unload" in kinds
