"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Message:
    """A single chat message."""

    role: str
    content: str


class LLMProvider(ABC):
    """Model-agnostic interface for text completion."""

    name: str

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,
        *,
        request_timeout: float | None = None,
    ) -> str:
        """Return the model's text response for the given messages.

        ``format`` is an optional JSON schema for grammar-constrained decoding;
        providers that support it (Ollama) emit schema-valid JSON, others ignore it.
        ``request_timeout`` optionally overrides the per-call read timeout (seconds)
        so short reasoning calls fail fast instead of hanging on a wedged backend;
        providers that don't support it ignore it.
        """

    @abstractmethod
    def ping(self) -> dict[str, Any]:
        """Lightweight connectivity/availability check."""

    @property
    @abstractmethod
    def default_model(self) -> str:
        """Default model identifier for this provider."""
