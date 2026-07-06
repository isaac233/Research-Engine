"""Load provider registry and instantiate LLM clients."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from research_engine.llm.anthropic_client import AnthropicClient
from research_engine.llm.ollama_client import OllamaClient
from research_engine.llm.provider import LLMProvider


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Immutable configuration for one provider."""

    name: str
    default_model: str
    roles: tuple[str, ...]
    context_window: int
    cost_tier: str
    rate_limit_rpm: int
    extra: dict[str, Any] = field(default_factory=dict)


class ModelRegistry:
    """Runtime registry of configured LLM providers."""

    def __init__(self, config_path: Path | str) -> None:
        self.config_path = Path(config_path)
        self._providers: dict[str, ProviderConfig] = {}
        self._role_defaults: dict[str, list[str]] = {}
        self._load()

    def _load(self) -> None:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Model registry not found: {self.config_path}")
        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Model registry must be a YAML mapping")

        providers = raw.get("providers", {})
        for name, cfg in providers.items():
            if not isinstance(cfg, dict):
                raise ValueError(f"Provider {name} config must be a mapping")
            roles = cfg.get("roles", [])
            self._providers[name] = ProviderConfig(
                name=name,
                default_model=cfg.get("default_model", ""),
                roles=tuple(roles) if isinstance(roles, list) else (),
                context_window=int(cfg.get("context_window", 0)),
                cost_tier=cfg.get("cost_tier", "unknown"),
                rate_limit_rpm=int(cfg.get("rate_limit_rpm", 0)),
                extra={k: v for k, v in cfg.items() if k not in {
                    "default_model", "roles", "context_window", "cost_tier", "rate_limit_rpm"
                }},
            )

        self._role_defaults = raw.get("role_defaults", {})
        for chain in self._role_defaults.values():
            if not isinstance(chain, list):
                raise ValueError("role_defaults values must be lists of provider names")
            for provider_name in chain:
                if provider_name not in self._providers:
                    raise ValueError(f"Unknown provider '{provider_name}' in role_defaults")

    def provider_names(self) -> set[str]:
        return set(self._providers.keys())

    def get_config(self, provider_name: str) -> ProviderConfig:
        if provider_name not in self._providers:
            raise KeyError(f"Unknown provider: {provider_name}")
        return self._providers[provider_name]

    def providers_for_role(self, role: str) -> list[str]:
        """Return the fallback provider chain for a role."""
        chain = self._role_defaults.get(role, [])
        if not chain:
            raise KeyError(f"No provider chain configured for role: {role}")
        return list(chain)

    def build_provider(self, provider_name: str) -> LLMProvider:
        """Instantiate a provider client from its config."""
        cfg = self.get_config(provider_name)
        extra = cfg.extra
        if provider_name == "ollama":
            return OllamaClient(
                base_url=extra.get("base_url", "http://localhost:11434"),
                default_model=cfg.default_model,
            )
        if provider_name == "anthropic":
            return AnthropicClient(
                api_key_env=extra.get("api_key_env", "ANTHROPIC_API_KEY"),
                default_model=cfg.default_model,
            )
        raise ValueError(f"Unsupported provider: {provider_name}")

    def get_provider_for_role(
        self, role: str, prefer_cost_tier: str | None = None
    ) -> LLMProvider:
        """Build the first available provider for a role."""
        chain = self.providers_for_role(role)
        for provider_name in chain:
            try:
                return self.build_provider(provider_name)
            except RuntimeError:
                continue
        raise RuntimeError(f"No available provider for role '{role}'")
