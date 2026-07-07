"""Tests for the model-stack validator."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from research_engine.config import EngineConfig
from research_engine.llm.model_registry import ModelRegistry
from research_engine.llm.validator import ModelStackValidator, ProviderValidation


def _write_registry(tmp_path: Path, content: dict[str, Any]) -> Path:
    path = tmp_path / "models.yaml"
    path.write_text(yaml.safe_dump(content), encoding="utf-8")
    return path


def test_validate_all_reports_provider_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "fake": {
                    "default_model": "m",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                }
            },
            "role_defaults": {"worker": ["fake"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class FakeProvider:
        name = "fake"
        _default_model = "m"

        def ping(self) -> dict[str, Any]:
            return {"ok": True, "models": ["m"]}

    monkeypatch.setattr(registry, "build_provider", lambda _name: FakeProvider())
    validator = ModelStackValidator(registry)
    results = validator.validate_all()

    assert len(results) == 1
    assert results[0] == ProviderValidation(
        name="fake",
        ok=True,
        default_model="m",
        details={"ok": True, "models": ["m"]},
    )


def test_validate_provider_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "bad": {
                    "default_model": "m",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                }
            },
            "role_defaults": {"worker": ["bad"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class BadProvider:
        name = "bad"

        def ping(self) -> dict[str, Any]:
            raise RuntimeError("boom")

    monkeypatch.setattr(registry, "build_provider", lambda _name: BadProvider())
    validator = ModelStackValidator(registry)
    result = validator.validate_provider("bad")

    assert not result.ok
    assert result.name == "bad"
    assert "RuntimeError" in (result.error or "")


def test_validate_model_available_found(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "ollama": {
                    "default_model": "gemma4",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                    "base_url": "http://localhost:11434",
                }
            },
            "role_defaults": {"worker": ["ollama"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class FakeOllama:
        def ping(self) -> dict[str, Any]:
            return {"ok": True, "models": ["gemma4", "qwen2"]}

    monkeypatch.setattr(registry, "build_provider", lambda _name: FakeOllama())
    validator = ModelStackValidator(registry)
    result = validator.validate_model_available("ollama", "qwen2")

    assert result.ok
    assert result.default_model == "qwen2"


def test_validate_model_available_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "ollama": {
                    "default_model": "gemma4",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                    "base_url": "http://localhost:11434",
                }
            },
            "role_defaults": {"worker": ["ollama"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class FakeOllama:
        def ping(self) -> dict[str, Any]:
            return {"ok": True, "models": ["gemma4"]}

    monkeypatch.setattr(registry, "build_provider", lambda _name: FakeOllama())
    validator = ModelStackValidator(registry)
    result = validator.validate_model_available("ollama", "missing")

    assert not result.ok
    assert "missing" in (result.error or "")


def test_validate_small_local_ok(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "ollama": {
                    "default_model": "gemma4",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                    "base_url": "http://localhost:11434",
                }
            },
            "role_defaults": {"worker": ["ollama"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class FakeOllama:
        def ping(self) -> dict[str, Any]:
            return {"ok": True, "models": ["qwen2:1.5b"]}

    monkeypatch.setattr(registry, "build_provider", lambda _name: FakeOllama())
    validator = ModelStackValidator(registry)
    result = validator.validate_small_local()

    assert result.ok
    assert result.default_model == "qwen2:1.5b"


def test_validate_small_local_none_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "ollama": {
                    "default_model": "gemma4",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                    "base_url": "http://localhost:11434",
                }
            },
            "role_defaults": {"worker": ["ollama"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class FakeOllama:
        def ping(self) -> dict[str, Any]:
            return {"ok": True, "models": ["big-model"]}

    monkeypatch.setattr(registry, "build_provider", lambda _name: FakeOllama())
    validator = ModelStackValidator(registry)
    result = validator.validate_small_local()

    assert not result.ok
    assert "small-capacity" in (result.error or "")


def test_validate_small_local_provider_failure(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "ollama": {
                    "default_model": "gemma4",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                    "base_url": "http://localhost:11434",
                }
            },
            "role_defaults": {"worker": ["ollama"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class FakeOllama:
        def ping(self) -> dict[str, Any]:
            return {"ok": False, "error": "down"}

    monkeypatch.setattr(registry, "build_provider", lambda _name: FakeOllama())
    validator = ModelStackValidator(registry)
    result = validator.validate_small_local()

    assert not result.ok
    assert "down" in (result.error or "")


def test_summarize(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    registry_path = _write_registry(
        tmp_path,
        {
            "providers": {
                "a": {
                    "default_model": "m1",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                },
                "b": {
                    "default_model": "m2",
                    "roles": ["worker"],
                    "context_window": 1000,
                    "cost_tier": "local",
                    "rate_limit_rpm": 10,
                },
            },
            "role_defaults": {"worker": ["a", "b"]},
        },
    )
    registry = ModelRegistry(registry_path)

    class Good:
        def ping(self) -> dict[str, Any]:
            return {"ok": True}

    class Bad:
        def ping(self) -> dict[str, Any]:
            return {"ok": False, "error": "nope"}

    monkeypatch.setattr(
        registry,
        "build_provider",
        lambda name: Good() if name == "a" else Bad(),
    )
    validator = ModelStackValidator(registry)
    summary = validator.summarize(validator.validate_all())

    assert summary["total"] == 2
    assert summary["healthy"] == 1
    assert summary["unhealthy"] == 1
    assert summary["all_healthy"] is False
    assert len(summary["providers"]) == 2


def test_from_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "models.yaml").write_text(
        yaml.safe_dump(
            {
                "providers": {
                    "fake": {
                        "default_model": "m",
                        "roles": ["worker"],
                        "context_window": 1000,
                        "cost_tier": "local",
                        "rate_limit_rpm": 10,
                    }
                },
                "role_defaults": {"worker": ["fake"]},
            }
        ),
        encoding="utf-8",
    )
    config = EngineConfig(tmp_path)
    monkeypatch.setattr(config, "model_registry_path", config_dir / "models.yaml")
    validator = ModelStackValidator.from_config(config)
    assert "fake" in validator.registry.provider_names()
