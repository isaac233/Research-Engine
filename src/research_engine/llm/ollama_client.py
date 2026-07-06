"""Ollama LLM client."""

from __future__ import annotations

from typing import Any

import httpx

from research_engine.llm.provider import LLMProvider, Message


class OllamaClient(LLMProvider):
    """Provider for local Ollama models."""

    name = "ollama"

    def __init__(self, base_url: str, default_model: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._default_model = default_model
        self.timeout = timeout

    @property
    def default_model(self) -> str:
        return self._default_model

    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        target_model = model or self._default_model
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {}) or {}
        return str(message.get("content", ""))

    def ping(self) -> dict[str, Any]:
        """Check that the Ollama server is reachable and lists at least one model."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                data = response.json()
            models = data.get("models", [])
            return {
                "ok": True,
                "models": [m.get("name", "") for m in models],
                "default": self._default_model,
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
