"""Ollama LLM client."""

from __future__ import annotations

import threading
from typing import Any

import httpx

from research_engine.llm.provider import LLMProvider, Message

_THINK_CLOSE = "</think>"


def _strip_reasoning(text: str) -> str:
    """Drop a leaked ``<think>…</think>`` preamble, keeping only the answer.

    Reasoning models (R1/Qwen3/Tongyi-DR) can leak their reasoning into ``content``
    even with ``think=false`` when the GGUF chat template ignores the flag. The real
    answer follows the final ``</think>``; everything before it is the preamble.
    ponytail: assumes prose never legitimately contains ``</think>`` (safe for
    reports); upgrade to a paired ``<think>…</think>`` regex if that ever bites.
    """
    idx = text.rfind(_THINK_CLOSE)
    return text[idx + len(_THINK_CLOSE) :].lstrip() if idx != -1 else text


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
        # One reused keep-alive client (see _http): a fresh client per call churned
        # connections under tight ranker/extract loops and stalled some in SYN_SENT.
        self._client: httpx.Client | None = None
        self._client_lock = threading.Lock()
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
        request_timeout: float | None = None,
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

        # A per-call timeout lets short reasoning calls (summarise/refine) fail fast on
        # a wedged Ollama scheduler instead of hanging for the full client timeout
        # (~300s), so the react loop skips that page and keeps its page budget.
        post_kwargs: dict[str, Any] = {"json": payload}
        if request_timeout is not None:
            post_kwargs["timeout"] = httpx.Timeout(
                request_timeout, connect=min(10.0, request_timeout)
            )
        response = self._http().post(f"{self.base_url}/api/chat", **post_kwargs)
        response.raise_for_status()
        data = response.json()

        message = data.get("message", {}) or {}
        return _strip_reasoning(str(message.get("content", "")))

    def _http(self) -> httpx.Client:
        """Return ONE reused keep-alive client, built lazily and thread-safely.

        A fresh ``httpx.Client`` per call opened a new TCP connection every time;
        under the ranker/extractor's tight call loops that churned connections and
        left some stuck in SYN_SENT — connect stalls that froze a whole collect for
        minutes even though Ollama answered a single request in <1s. A pooled,
        keep-alive client removes the per-call handshake. ``httpx.Client`` is safe to
        share across the extract thread pool. Timeout is split so a stuck TCP connect
        fails in 10s while a slow generation keeps the full read budget.
        """
        client = self._client
        if client is not None and not client.is_closed:
            return client
        with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.Client(
                    timeout=httpx.Timeout(self.timeout, connect=min(10.0, self.timeout)),
                    limits=httpx.Limits(max_keepalive_connections=8, max_connections=16),
                )
            return self._client

    def close(self) -> None:
        """Close the reused client (best-effort; safe to call repeatedly)."""
        client = self._client
        if client is not None and not client.is_closed:
            client.close()

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
