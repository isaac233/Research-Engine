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


def test_registry_rejects_non_dict_role_defaults(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        "providers: {}\nrole_defaults: not_a_dict\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="role_defaults must be a mapping"):
        ModelRegistry(path)


def test_registry_rejects_unsafe_ollama_url(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        """
providers:
  ollama:
    default_model: m
    roles: [worker]
    context_window: 1000
    cost_tier: local
    rate_limit_rpm: 10
    base_url: http://evil.com:11434
role_defaults:
  worker: [ollama]
""",
        encoding="utf-8",
    )
    registry = ModelRegistry(path)
    with pytest.raises(ValueError, match="local origin"):
        registry.build_provider("ollama")


def test_registry_rejects_unsupported_api_key_env(tmp_path: Path) -> None:
    path = tmp_path / "models.yaml"
    path.write_text(
        """
providers:
  anthropic:
    default_model: m
    roles: [auditor]
    context_window: 1000
    cost_tier: premium
    rate_limit_rpm: 10
    api_key_env: PATH
role_defaults:
  auditor: [anthropic]
""",
        encoding="utf-8",
    )
    registry = ModelRegistry(path)
    with pytest.raises(ValueError, match="Unsupported Anthropic API key env var"):
        registry.build_provider("anthropic")
