"""Project path resolution and engine configuration."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


class EngineConfig:
    """Runtime paths and loaded configuration for the engine."""

    DEFAULTS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default.yaml"
    MODEL_REGISTRY_ENV = "RESEARCH_ENGINE_MODEL_REGISTRY"

    def __init__(
        self,
        project_root: Path | str | None = None,
        config_overrides: dict[str, Any] | None = None,
        model_registry_path: Path | str | None = None,
    ) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.research_dir = self.project_root / "Research"
        self.engine_data_dir = self.project_root / "data"
        self.model_registry_path = self._resolve_model_registry_path(model_registry_path)
        self._config = self._load_defaults()
        if config_overrides:
            self._config = self._deep_merge(self._config, config_overrides)

    def _resolve_model_registry_path(self, override: Path | str | None) -> Path:
        """Return the model registry path, honoring explicit/env overrides."""
        if override is not None:
            return Path(override)
        env_path = os.environ.get(self.MODEL_REGISTRY_ENV)
        if env_path:
            return Path(env_path)
        project_config = self.project_root / "config" / "models.yaml"
        if project_config.exists():
            return project_config
        return Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"

    def _load_defaults(self) -> dict[str, Any]:
        """Load default.yaml if present; otherwise return an empty config."""
        if self.DEFAULTS_PATH.exists():
            with self.DEFAULTS_PATH.open(encoding="utf-8") as fh:
                return yaml.safe_load(fh) or {}
        return {}

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Merge nested dictionaries; override values replace leaf values."""
        merged = dict(base)
        for key, value in override.items():
            if (
                key in merged
                and isinstance(merged[key], dict)
                and isinstance(value, dict)
            ):
                merged[key] = EngineConfig._deep_merge(merged[key], value)
            else:
                merged[key] = value
        return merged

    def get(self, key: str, default: Any = None) -> Any:
        """Return a configuration value by dotted key, e.g. ``browser.timeout``."""
        parts = key.split(".")
        value: Any = self._config
        for part in parts:
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def as_dict(self) -> dict[str, Any]:
        """Return a shallow copy of the loaded configuration."""
        return dict(self._config)

    def campaign_paths(self, slug: str) -> tuple[Path, Path]:
        """Return (campaign_dir, campaign_insights_path) for a slug."""
        campaign_dir = self.research_dir / slug
        insights_path = campaign_dir / f"{slug}_Insights.MD"
        return campaign_dir, insights_path

    def master_insights_path(self) -> Path:
        """Return the aggregated master insights path."""
        return self.research_dir / "Insights.MD"

    def state_db_path(self) -> Path:
        """Return the SQLite state DB path inside engine data dir."""
        return self.engine_data_dir / "state.db"

    def cache_db_path(self) -> Path:
        """Return the SQLite source cache DB path inside engine data dir."""
        return self.engine_data_dir / "cache.db"

    def source_memory_db_path(self) -> Path:
        """Return the SQLite source-memory DB path inside engine data dir."""
        return self.engine_data_dir / "source_memory.db"

    def agent_history_db_path(self) -> Path:
        """Return the SQLite agent-history audit DB path inside engine data dir."""
        return self.engine_data_dir / "agent_history.db"
