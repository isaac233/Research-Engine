"""Model lane roster loaded from config/model_lanes.yaml.

A lane maps a task role to a model tag (with an installed fallback). When a
pull report is present, the lane's effective tag is the tag that actually
resolved (requested tag if pulled, else the fallback) so callers never address
a tag that 404'd.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True, slots=True)
class Lane:
    name: str
    role: str
    tag: str  # effective tag (post pull-report resolution)
    requested_tag: str
    fallback: str
    est_vram_gb: float
    fits_in_vram: bool
    num_ctx: int
    enabled: bool
    use: str


class LaneRoster:
    """Collection of configured lanes with role/name lookup."""

    def __init__(self, lanes: list[Lane]) -> None:
        self._lanes = {lane.name: lane for lane in lanes}

    @classmethod
    def from_yaml(cls, path: Path | str, pull_report: Path | str | None = None) -> LaneRoster:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        lane_cfgs = raw.get("lanes", {}) if isinstance(raw, dict) else {}
        resolved = _load_resolved_tags(pull_report)

        lanes: list[Lane] = []
        for name, cfg in lane_cfgs.items():
            requested = str(cfg.get("tag", ""))
            effective = resolved.get(name, requested)
            lanes.append(
                Lane(
                    name=name,
                    role=str(cfg.get("role", "")),
                    tag=effective,
                    requested_tag=requested,
                    fallback=str(cfg.get("fallback", "")),
                    est_vram_gb=float(cfg.get("est_vram_gb", 0)),
                    fits_in_vram=bool(cfg.get("fits_in_vram", False)),
                    num_ctx=int(cfg.get("num_ctx", 8192)),
                    enabled=bool(cfg.get("enabled", True)),
                    use=str(cfg.get("use", "")),
                )
            )
        return cls(lanes)

    def lane(self, name: str) -> Lane:
        if name not in self._lanes:
            raise KeyError(f"Unknown lane: {name}")
        return self._lanes[name]

    def lane_for_role(self, role: str) -> Lane | None:
        """First enabled lane serving a role, or None."""
        for lane in self._lanes.values():
            if lane.role == role and lane.enabled:
                return lane
        return None

    def enabled_lanes(self) -> list[Lane]:
        return [lane for lane in self._lanes.values() if lane.enabled]

    def all_lanes(self) -> list[Lane]:
        return list(self._lanes.values())


def _load_resolved_tags(pull_report: Path | str | None) -> dict[str, str]:
    """Map lane name -> resolved tag from the pull report, if it exists."""
    if pull_report is None:
        return {}
    path = Path(pull_report)
    if not path.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    resolved: dict[str, str] = {}
    for result in data.get("results", []):
        name = result.get("lane")
        tag = result.get("resolved_tag")
        if name and tag:
            resolved[name] = str(tag)
    return resolved
