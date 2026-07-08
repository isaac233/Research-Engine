"""Model-stack validation for configured LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.config import EngineConfig
from research_engine.llm.model_registry import ModelRegistry


@dataclass(frozen=True)
class ProviderValidation:
    """Result of validating a single provider."""

    name: str
    ok: bool
    default_model: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class ModelStackValidator:
    """Ping every configured provider and report stack health."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    @classmethod
    def from_config(cls, config: EngineConfig | None = None) -> ModelStackValidator:
        config = config or EngineConfig()
        registry = ModelRegistry(config.model_registry_path)
        return cls(registry)

    def validate_all(self) -> list[ProviderValidation]:
        """Ping every provider in the registry."""
        results: list[ProviderValidation] = []
        for name in sorted(self.registry.provider_names()):
            results.append(self.validate_provider(name))
        return results

    def validate_provider(self, name: str) -> ProviderValidation:
        """Ping a single provider by name."""
        cfg = self.registry.get_config(name)
        try:
            provider = self.registry.build_provider(name)
            details = provider.ping()
            return ProviderValidation(
                name=name,
                ok=bool(details.get("ok")),
                default_model=cfg.default_model,
                details=details,
                error=details.get("error"),
            )
        except Exception as exc:  # noqa: BLE001
            return ProviderValidation(
                name=name,
                ok=False,
                default_model=cfg.default_model,
                error=f"{type(exc).__name__}: {exc}",
            )

    def validate_model_available(self, provider_name: str, model_name: str) -> ProviderValidation:
        """Check that a specific model is served by a provider."""
        result = self.validate_provider(provider_name)
        if not result.ok:
            return result

        available = result.details.get("models", [])
        if model_name not in available:
            return ProviderValidation(
                name=provider_name,
                ok=False,
                default_model=model_name,
                details=result.details,
                error=f"Model '{model_name}' not found in available models: {available}",
            )
        return ProviderValidation(
            name=provider_name,
            ok=True,
            default_model=model_name,
            details=result.details,
        )

    SMALL_MODEL_PREFIXES = ("gemma", "qwen", "phi")
    DEFAULT_LOCAL_PROVIDER = "ollama"

    def validate_small_local(self, provider_name: str = DEFAULT_LOCAL_PROVIDER) -> ProviderValidation:
        """Validate that a small local model (Gemma/Qwen/Phi class) is available."""
        result = self.validate_provider(provider_name)
        if not result.ok:
            return result

        available = result.details.get("models", [])
        small_models = [
            name
            for name in available
            if any(prefix in name.lower() for prefix in self.SMALL_MODEL_PREFIXES)
        ]
        if not small_models:
            prefixes = ", ".join(self.SMALL_MODEL_PREFIXES)
            return ProviderValidation(
                name=provider_name,
                ok=False,
                default_model=result.default_model,
                details=result.details,
                error=f"No small-capacity model ({prefixes}) found in {provider_name}",
            )
        return ProviderValidation(
            name=provider_name,
            ok=True,
            default_model=small_models[0],
            details=result.details,
        )

    def validate_lanes(self, roster: Any) -> list[dict[str, Any]]:
        """Check each lane's effective tag against installed Ollama models."""
        ping = self.validate_provider("ollama")
        installed = set(ping.details.get("models", [])) if ping.ok else set()
        report: list[dict[str, Any]] = []
        for lane in roster.all_lanes():
            report.append(
                {
                    "lane": lane.name,
                    "role": lane.role,
                    "tag": lane.tag,
                    "requested_tag": lane.requested_tag,
                    "available": lane.tag in installed,
                    "used_fallback": lane.tag != lane.requested_tag,
                    "fits_in_vram": lane.fits_in_vram,
                    "est_vram_gb": lane.est_vram_gb,
                    "enabled": lane.enabled,
                }
            )
        return report

    @staticmethod
    def summarize(results: list[ProviderValidation]) -> dict[str, Any]:
        """Return a concise summary of validation results."""
        total = len(results)
        healthy = [r for r in results if r.ok]
        unhealthy = [r for r in results if not r.ok]
        return {
            "total": total,
            "healthy": len(healthy),
            "unhealthy": len(unhealthy),
            "all_healthy": len(healthy) == total and total > 0,
            "providers": [
                {"name": r.name, "ok": r.ok, "default_model": r.default_model, "error": r.error}
                for r in results
            ],
        }


def validate_model_stack(config: EngineConfig | None = None) -> dict[str, Any]:
    """Convenience function: validate the full configured model stack."""
    validator = ModelStackValidator.from_config(config)
    return validator.summarize(validator.validate_all())
