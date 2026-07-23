"""Anthropic LLM client."""

from __future__ import annotations

import os
from typing import Any

import anthropic as anthropic_sdk

from research_engine.llm.provider import LLMProvider, Message


class AnthropicClient(LLMProvider):
    """Provider for Anthropic Claude models."""

    name = "anthropic"

    def __init__(self, api_key_env: str, default_model: str) -> None:
        self.api_key_env = api_key_env
        self._default_model = default_model
        self._api_key = self._require_api_key()
        self._client = anthropic_sdk.Anthropic(api_key=self._api_key)

    @property
    def default_model(self) -> str:
        return self._default_model

    def _require_api_key(self) -> str:
        key = os.environ.get(self.api_key_env)
        if not key:
            raise RuntimeError(
                f"Anthropic provider requires {self.api_key_env} environment variable"
            )
        return key

    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,  # noqa: ARG002 — Anthropic uses tools, not schema
        request_timeout: float | None = None,  # noqa: ARG002 — client-managed timeout
    ) -> str:
        target_model = model or self._default_model
        system_message = ""
        chat_messages: list[dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_message = message.content
            else:
                chat_messages.append({"role": message.role, "content": message.content})

        kwargs: dict[str, Any] = {
            "model": target_model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 1024,
        }
        if system_message:
            kwargs["system"] = system_message

        response = self._client.messages.create(**kwargs)
        return response.content[0].text if response.content else ""

    def ping(self) -> dict[str, Any]:
        """Validate that the API key is present and the client can be built."""
        try:
            return {
                "ok": bool(self._api_key),
                "default": self._default_model,
                "api_key_present": bool(self._api_key),
            }
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
