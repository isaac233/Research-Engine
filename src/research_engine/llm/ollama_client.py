"""Ollama LLM client."""

from __future__ import annotations

from typing import Any

import httpx

from research_engine.llm.provider import LLMProvider, Message


class OllamaClient(LLMProvider):
    """Provider for local Ollama models."""

    name = "ollama"

    def __init__(
        self,
        base_url: str,
        default_model: str,
        timeout: float = 120.0,
        think: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._default_model = default_model
        self.timeout = timeout
        # Thinking models (e.g. gemma4) otherwise spend the token budget on a
        # hidden reasoning preamble and return empty content. The engine wants
        # direct structured output, so disable thinking by default.
        self.think = think

    @property
    def default_model(self) -> str:
        return self._default_model

    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
        keep_alive: str | int | None = None,
    ) -> str:
        target_model = model or self._default_model
        opts: dict[str, Any] = {"temperature": temperature}
        if options:
            opts.update(options)  # e.g. num_ctx, num_gpu, num_predict
        if max_tokens is not None:
            opts["num_predict"] = max_tokens
        payload: dict[str, Any] = {
            "model": target_model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": False,
            "think": self.think,
            "options": opts,
        }
        # Grammar-constrained decoding: a JSON schema forces schema-valid output.
        if format is not None:
            payload["format"] = format
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {}) or {}
        return str(message.get("content", ""))

    def ps(self) -> list[dict[str, Any]]:
        """Return models currently loaded in memory (GET /api/ps)."""
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/ps")
                response.raise_for_status()
                data = response.json()
        except Exception:  # noqa: BLE001 - treat probe failure as "nothing loaded"
            return []
        models = data.get("models", []) or []
        return [m for m in models if isinstance(m, dict)]

    def warm(
        self,
        model: str,
        keep_alive: str | int = "5m",
        options: dict[str, Any] | None = None,
    ) -> bool:
        """Load a model into memory (empty /api/generate with keep_alive)."""
        payload: dict[str, Any] = {"model": model, "keep_alive": keep_alive}
        if options:
            payload["options"] = options
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
        except Exception:  # noqa: BLE001
            return False
        return True

    def unload(self, model: str) -> bool:
        """Evict a model from memory (keep_alive=0)."""
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.base_url}/api/generate",
                    json={"model": model, "keep_alive": 0},
                )
                response.raise_for_status()
        except Exception:  # noqa: BLE001
            return False
        return True

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
