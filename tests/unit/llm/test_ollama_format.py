"""Grammar-constrained decoding: the Ollama payload carries a JSON-schema ``format``.

Ollama supports schema-constrained decoding via a top-level ``format`` field
(llama.cpp GBNF). Threading it makes small models emit valid JSON ~always, so the
agentic JSON steps (query decomposition, outline, deepen) stop degrading to their
weak fallbacks on a parse miss.
"""

from __future__ import annotations

from typing import Any

import httpx

from research_engine.llm.ollama_client import OllamaClient
from research_engine.llm.provider import Message


class _Resp:
    def raise_for_status(self) -> None:  # noqa: D401
        return None

    def json(self) -> dict[str, Any]:
        return {"message": {"content": "ok"}}


def _capture(monkeypatch: Any) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_post(self: Any, url: str, json: dict[str, Any] | None = None, **kw: Any) -> _Resp:
        captured["payload"] = json
        return _Resp()

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    return captured


def test_format_included_when_schema_passed(monkeypatch: Any) -> None:
    captured = _capture(monkeypatch)
    schema = {"type": "object", "properties": {"queries": {"type": "array"}}}
    OllamaClient("http://x", "m").complete([Message("user", "hi")], format=schema)
    assert captured["payload"]["format"] == schema


def test_format_omitted_by_default(monkeypatch: Any) -> None:
    captured = _capture(monkeypatch)
    OllamaClient("http://x", "m").complete([Message("user", "hi")])
    assert "format" not in captured["payload"]
