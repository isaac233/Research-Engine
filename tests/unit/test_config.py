"""Unit tests for engine path and YAML configuration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from research_engine.config import EngineConfig


def test_default_paths_use_cwd(tmp_path: Path) -> None:
    config = EngineConfig(tmp_path)
    assert config.project_root == tmp_path
    assert config.research_dir == tmp_path / "Research"
    assert config.engine_data_dir == tmp_path / "data"


def test_campaign_paths() -> None:
    config = EngineConfig(Path("/tmp/project"))
    campaign_dir, insights = config.campaign_paths("my_campaign")
    assert campaign_dir == Path("/tmp/project/Research/my_campaign")
    assert insights == Path("/tmp/project/Research/my_campaign/my_campaign_Insights.MD")


def test_master_insights_path() -> None:
    config = EngineConfig(Path("/tmp/project"))
    assert config.master_insights_path() == Path("/tmp/project/Research/Insights.MD")


def test_db_paths() -> None:
    config = EngineConfig(Path("/tmp/project"))
    assert config.state_db_path() == Path("/tmp/project/data/state.db")
    assert config.cache_db_path() == Path("/tmp/project/data/cache.db")


def test_load_default_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    defaults = {
        "browser": {"timeout": 42, "max_retries": 7},
        "unpaywall": {"email": "test@example.com"},
    }
    (config_dir / "default.yaml").write_text(yaml.safe_dump(defaults), encoding="utf-8")

    monkeypatch.setattr(EngineConfig, "DEFAULTS_PATH", config_dir / "default.yaml")
    config = EngineConfig(tmp_path)

    assert config.get("browser.timeout") == 42
    assert config.get("browser.max_retries") == 7
    assert config.get("unpaywall.email") == "test@example.com"


def test_missing_default_yaml_uses_empty_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(EngineConfig, "DEFAULTS_PATH", tmp_path / "missing.yaml")
    config = EngineConfig(tmp_path)
    assert config.get("browser.timeout") is None
    assert config.as_dict() == {}


def test_config_overrides_merge_with_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text(
        yaml.safe_dump({"browser": {"timeout": 10}}), encoding="utf-8"
    )
    monkeypatch.setattr(EngineConfig, "DEFAULTS_PATH", config_dir / "default.yaml")

    config = EngineConfig(tmp_path, config_overrides={"browser": {"timeout": 99}})
    assert config.get("browser.timeout") == 99


def test_config_overrides_deep_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default.yaml").write_text(
        yaml.safe_dump({"browser": {"timeout": 10, "max_retries": 3}}), encoding="utf-8"
    )
    monkeypatch.setattr(EngineConfig, "DEFAULTS_PATH", config_dir / "default.yaml")

    config = EngineConfig(tmp_path, config_overrides={"browser": {"timeout": 99}})
    assert config.get("browser.timeout") == 99
    assert config.get("browser.max_retries") == 3


def test_model_registry_path_prefers_project_config(tmp_path: Path) -> None:
    project_config = tmp_path / "config" / "models.yaml"
    project_config.parent.mkdir(parents=True)
    project_config.write_text("providers: {}\nrole_defaults: {}\n", encoding="utf-8")
    config = EngineConfig(tmp_path)
    assert config.model_registry_path == project_config


def test_model_registry_path_constructor_override(tmp_path: Path) -> None:
    override = tmp_path / "custom.yaml"
    override.write_text("providers: {}\nrole_defaults: {}\n", encoding="utf-8")
    config = EngineConfig(tmp_path, model_registry_path=override)
    assert config.model_registry_path == override


def test_model_registry_path_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_path = tmp_path / "env_models.yaml"
    env_path.write_text("providers: {}\nrole_defaults: {}\n", encoding="utf-8")
    monkeypatch.setenv(EngineConfig.MODEL_REGISTRY_ENV, str(env_path))
    config = EngineConfig(tmp_path)
    assert config.model_registry_path == env_path


def test_get_returns_default_for_unknown_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(EngineConfig, "DEFAULTS_PATH", tmp_path / "missing.yaml")
    config = EngineConfig(tmp_path)
    assert config.get("does.not.exist", "fallback") == "fallback"


def test_serp_endpoint_unset_is_none() -> None:
    import os
    os.environ.pop(EngineConfig.SERP_ENDPOINT_ENV, None)
    assert EngineConfig().serp_endpoint is None


def test_serp_endpoint_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    ep = "http://localhost:8080/search?q={query}&format=json"
    monkeypatch.setenv(EngineConfig.SERP_ENDPOINT_ENV, ep)
    assert EngineConfig().serp_endpoint == ep
