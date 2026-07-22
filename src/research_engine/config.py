"""Project path resolution and engine configuration."""

from __future__ import annotations

import logging
import os
from collections.abc import MutableMapping
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

PROFILE_ENV = "RESEARCH_ENGINE_PROFILE"

# Named env presets: one switch expands to a proven flag set. Applied with
# ``setdefault`` semantics (explicit env always wins) so the default path stays
# byte-identical when unset. See ``apply_profile``.
#
# ``vague`` = the measured task-53 winning stack (2026-07-21 cache-isolated A/B,
# Kimi judge). It reproduces the ``warp`` A/B cell — RACE 34.32 / FACT 80.0%, the
# top cell — which is the react path + evidence-grounded scope (R1/R2) + WARP
# writer (R4) layered on the dependency-safe fetchability levers. It deliberately
# EXCLUDES the levers the same A/B showed hurt this task class: R3 ephemeral gap
# (FACT 57.6%), R5 Tongyi-DR reasoning lane (RACE 22.07, worst), and R6 evidence
# ranker (coverage-capping; FACT-first only). Machine infra (SERP endpoint,
# replay cache, worker count) is left to the runtime. N=1 — opt-in, not a default.
_PROFILES: dict[str, dict[str, str]] = {
    "vague": {
        # react retrieval path — the v9 quality levers only fire here
        "RESEARCH_ENGINE_PLANNER": "react",
        "RESEARCH_ENGINE_REACT_SKIP_COLLECT": "1",
        "RESEARCH_ENGINE_REACT_MAX_PAGES": "48",
        "RESEARCH_ENGINE_REACT_SEEDED_OUTLINE": "1",
        "RESEARCH_ENGINE_REACT_PER_OBJECTIVE_SEARCHES": "3",
        "RESEARCH_ENGINE_WRITER_MAX_SENTENCES": "16",
        "RESEARCH_ENGINE_WRITER_MAX_TOKENS": "2400",
        # dependency-safe fetchability levers (degrade gracefully)
        "RESEARCH_ENGINE_CDP_FALLBACK": "1",
        "RESEARCH_ENGINE_PDF_INGEST": "1",
        "RESEARCH_ENGINE_WAYBACK_FALLBACK": "1",
        # v9 vague-cohort delta: evidence-grounded scope (R1/R2) + WARP writer (R4)
        "RESEARCH_ENGINE_RUBRIC_SCAFFOLD": "1",
        "RESEARCH_ENGINE_SCOPING_PASS": "1",
        "RESEARCH_ENGINE_RUBRIC_CRITIC": "1",
        "RESEARCH_ENGINE_WARP_WRITER": "1",
        "RESEARCH_ENGINE_WARP_ROUNDS": "3",
        # v10 V1 exposure lever — the one validated win: sentence-window spans lift
        # FACT + RACE (task-53 frozen A/B +1.8 RACE/+5.4pt FACT; task-57 +2.6 RACE,
        # class-proven). arXiv:2607.12257 exposure bound. Additive on the warp stack.
        "RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES": "2",
        "RESEARCH_ENGINE_SPAN_WINDOW_CHARS": "1024",
    },
}


def apply_profile(environ: MutableMapping[str, str] | None = None) -> str | None:
    """Expand ``RESEARCH_ENGINE_PROFILE`` into its flag set via ``setdefault``.

    Explicit env vars win (setdefault only fills unset keys). Unknown/empty
    profile is a no-op. Returns the applied profile name, or ``None``.
    """
    env = os.environ if environ is None else environ
    name = (env.get(PROFILE_ENV) or "").strip().lower()
    if not name:
        return None
    flags = _PROFILES.get(name)
    if flags is None:
        logger.warning("Unknown %s=%r; known: %s", PROFILE_ENV, name, ", ".join(_PROFILES))
        return None
    for key, value in flags.items():
        env.setdefault(key, value)  # explicit env wins
    logger.info("Applied profile %r (%d flags)", name, len(flags))
    return name


class EngineConfig:
    """Runtime paths and loaded configuration for the engine."""

    DEFAULTS_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "default.yaml"
    MODEL_REGISTRY_ENV = "RESEARCH_ENGINE_MODEL_REGISTRY"
    # A SearXNG (or compatible) JSON endpoint template, e.g.
    #   http://localhost:8080/search?q={query}&format=json
    # When set, the web `serp` discovery source is enabled; unset = academic-only.
    SERP_ENDPOINT_ENV = "RESEARCH_ENGINE_SERP_ENDPOINT"

    # Comma-separated URL substrings dropped from web search results, e.g.
    # benchmark-dataset hosts during bench runs (leakage guard).
    SERP_BLOCKLIST_ENV = "RESEARCH_ENGINE_SERP_BLOCKLIST"

    @property
    def serp_endpoint(self) -> str | None:
        """Web-search endpoint template from env, or None if unconfigured."""
        return os.environ.get(self.SERP_ENDPOINT_ENV) or None

    @property
    def serp_blocklist(self) -> tuple[str, ...]:
        """URL substrings to exclude from web search results."""
        raw = os.environ.get(self.SERP_BLOCKLIST_ENV, "")
        return tuple(part.strip() for part in raw.split(",") if part.strip())

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
