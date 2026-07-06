"""Unit tests for the model-agnostic LLM registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_engine.llm.model_registry import ModelRegistry


def test_registry_loads_config() -> None:
    registry = ModelRegistry(Path("config/models.yaml"))
    assert registry.provider_names() == {"ollama", "anthropic"}


def test_registry_role_chain() -> None:
    registry = ModelRegistry(Path("config/models.yaml"))
    assert registry.providers_for_role("planner") == ["ollama"]
    assert registry.providers_for_role("auditor") == ["anthropic", "ollama"]


def test_registry_rejects_unknown_provider() -> None:
    registry = ModelRegistry(Path("config/models.yaml"))
    with pytest.raises(KeyError):
        registry.get_config("unknown")


def test_registry_builds_ollama() -> None:
    registry = ModelRegistry(Path("config/models.yaml"))
    provider = registry.build_provider("ollama")
    assert provider.name == "ollama"
    assert provider.default_model == "gemma4"


def test_registry_builds_anthropic_without_key() -> None:
    registry = ModelRegistry(Path("config/models.yaml"))
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        registry.build_provider("anthropic")
