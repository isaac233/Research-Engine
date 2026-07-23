"""GPU + model-residency probe so the user can SEE the local model working.

Shells ``nvidia-smi`` for VRAM and reads Ollama ``/api/ps`` for the per-model
RAM-offload split. Everything is best-effort: on a machine without an NVIDIA
GPU (or in CI) ``snapshot()`` returns ``None`` rather than raising.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Any, Protocol


class _PsClient(Protocol):
    def ps(self) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class LoadedModel:
    name: str
    size_mb: float
    size_vram_mb: float

    @property
    def offload_pct(self) -> float:
        """Fraction of the model living in system RAM (0.0 = fully on GPU)."""
        if self.size_mb <= 0:
            return 0.0
        ram = max(self.size_mb - self.size_vram_mb, 0.0)
        return round(ram / self.size_mb, 3)


@dataclass(frozen=True, slots=True)
class GpuSnapshot:
    vram_used_mb: float
    vram_total_mb: float
    loaded_models: list[LoadedModel] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "vram_used_mb": self.vram_used_mb,
            "vram_total_mb": self.vram_total_mb,
            "models": [
                {
                    "name": m.name,
                    "size_mb": m.size_mb,
                    "size_vram_mb": m.size_vram_mb,
                    "offload_pct": m.offload_pct,
                }
                for m in self.loaded_models
            ],
        }


class GpuProbe:
    """Probe VRAM usage and Ollama model residency."""

    def __init__(self, ollama_client: _PsClient | None = None) -> None:
        self.ollama_client = ollama_client

    def snapshot(self) -> GpuSnapshot | None:
        vram = self._nvidia_smi()
        if vram is None:
            return None
        used, total = vram
        return GpuSnapshot(
            vram_used_mb=used,
            vram_total_mb=total,
            loaded_models=self._loaded_models(),
        )

    @staticmethod
    def _nvidia_smi() -> tuple[float, float] | None:
        try:
            proc = subprocess.run(  # noqa: S603,S607 (fixed local CLI)
                [
                    "nvidia-smi",
                    "--query-gpu=memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return None
        if proc.returncode != 0:
            return None
        line = proc.stdout.decode("utf-8", "replace").strip().splitlines()
        if not line:
            return None
        try:
            used_str, total_str = line[0].split(",")
            return (float(used_str.strip()), float(total_str.strip()))
        except (ValueError, IndexError):
            return None

    def _loaded_models(self) -> list[LoadedModel]:
        if self.ollama_client is None:
            return []
        try:
            entries = self.ollama_client.ps()
        except Exception:  # noqa: BLE001
            return []
        models: list[LoadedModel] = []
        for entry in entries:
            size = float(entry.get("size", 0) or 0) / 1_000_000
            size_vram = float(entry.get("size_vram", 0) or 0) / 1_000_000
            models.append(
                LoadedModel(
                    name=str(entry.get("name", "")),
                    size_mb=round(size, 1),
                    size_vram_mb=round(size_vram, 1),
                )
            )
        return models


def _demo() -> None:
    m = LoadedModel(name="x", size_mb=1000.0, size_vram_mb=600.0)
    assert m.offload_pct == 0.4, m.offload_pct
    assert LoadedModel("y", 0.0, 0.0).offload_pct == 0.0
    snap = GpuSnapshot(1000.0, 16000.0, [m])
    assert snap.as_dict()["models"][0]["offload_pct"] == 0.4
    print("gpu_probe demo ok")


if __name__ == "__main__":
    _demo()
