"""Sequential model load/unload manager.

Seven lanes cannot co-reside in 16GB VRAM, so the engine loads one model,
runs its steps, evicts it (keep_alive=0), and loads the next. This manager
owns that lifecycle and records switch events.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from research_engine.llm.ollama_client import OllamaClient

EventHook = Callable[[str, dict[str, Any]], None]


class ModelLifecycleManager:
    """Load/unload/switch Ollama models one at a time."""

    def __init__(self, client: OllamaClient, on_event: EventHook | None = None) -> None:
        self.client = client
        self._on_event = on_event
        self._current: str | None = None

    @property
    def current(self) -> str | None:
        return self._current

    def _emit(self, event: str, **payload: Any) -> None:
        if self._on_event is not None:
            self._on_event(event, payload)

    def active(self) -> list[str]:
        """Model tags currently loaded in memory."""
        return [str(m.get("name", "")) for m in self.client.ps()]

    def load(self, tag: str, num_ctx: int | None = None, keep_alive: str | int = "5m") -> bool:
        options = {"num_ctx": num_ctx} if num_ctx else None
        ok = self.client.warm(tag, keep_alive=keep_alive, options=options)
        if ok:
            self._current = tag
        self._emit("model_load", tag=tag, ok=ok, num_ctx=num_ctx)
        return ok

    def unload(self, tag: str) -> bool:
        ok = self.client.unload(tag)
        if self._current == tag:
            self._current = None
        self._emit("model_unload", tag=tag, ok=ok)
        return ok

    def switch(self, to_tag: str, num_ctx: int | None = None) -> bool:
        """Evict the current model (if any) and load ``to_tag``."""
        from_tag = self._current
        if from_tag and from_tag != to_tag:
            self.unload(from_tag)
        self._emit("model_switch", from_tag=from_tag, to_tag=to_tag)
        if from_tag == to_tag:
            return True
        return self.load(to_tag, num_ctx=num_ctx)

    @contextmanager
    def with_model(self, tag: str, num_ctx: int | None = None) -> Iterator[str]:
        """Load a model for a block, guaranteeing eviction on exit (even on error)."""
        self.switch(tag, num_ctx=num_ctx)
        try:
            yield tag
        finally:
            self.unload(tag)
