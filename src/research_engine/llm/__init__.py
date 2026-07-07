"""Model-agnostic LLM provider layer.

Client classes are imported lazily via ``__getattr__`` so that the package
namespace works even when the optional ``anthropic`` or ``ollama`` runtime
dependencies are not installed. Direct submodule imports continue to work as
before.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from research_engine.llm.model_registry import ModelRegistry
from research_engine.llm.provider import LLMProvider, Message

if TYPE_CHECKING:
    from research_engine.llm.anthropic_client import AnthropicClient
    from research_engine.llm.ollama_client import OllamaClient

__all__ = [
    "AnthropicClient",
    "LLMProvider",
    "Message",
    "ModelRegistry",
    "OllamaClient",
]


def __getattr__(name: str) -> Any:
    if name == "AnthropicClient":
        from research_engine.llm.anthropic_client import AnthropicClient

        return AnthropicClient
    if name == "OllamaClient":
        from research_engine.llm.ollama_client import OllamaClient

        return OllamaClient
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
