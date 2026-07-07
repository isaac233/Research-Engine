"""Artifact manager: writes campaign insight briefs and the master Research/Insights.MD."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from research_engine.config import EngineConfig


class ArtifactManager:
    """Write deliverables to the host project's `Research/` layout."""

    def __init__(self, config: EngineConfig) -> None:
        self.config = config

    def write_campaign_brief(self, slug: str, brief: str, evidence_map: dict[str, Any] | None = None) -> Path:
        """Write a single campaign's insight brief and evidence map."""
        campaign_dir, insights_path = self.config.campaign_paths(slug)
        self._guard_campaign_dir(campaign_dir)
        campaign_dir.mkdir(parents=True, exist_ok=True)
        insights_path.write_text(brief, encoding="utf-8")
        if evidence_map is not None:
            evidence_path = campaign_dir / "evidence_map.json"
            self._guard_campaign_dir(evidence_path)
            evidence_path.write_text(json.dumps(evidence_map, indent=2, default=str), encoding="utf-8")
        return insights_path

    def _guard_campaign_dir(self, path: Path) -> None:
        """Raise if a campaign path escapes the configured Research directory."""
        base = self.config.research_dir.resolve()
        target = path.resolve()
        if base not in target.parents and target != base:
            raise ValueError(f"Campaign path {path} escapes research directory {self.config.research_dir}")

    def write_master_brief(self, campaigns: list[tuple[str, Path, str]]) -> Path:
        """Regenerate the aggregated master brief from all campaign briefs.

        `campaigns` is a list of (slug, insights_path, title) tuples.
        """
        master_path = self.config.master_insights_path()
        self.config.research_dir.mkdir(parents=True, exist_ok=True)
        lines: list[str] = [
            "# Research Insights",
            "",
            "Aggregated insight briefs from all research campaigns.",
            "",
            "## Campaigns",
            "",
        ]
        for slug, insights_path, title in campaigns:
            relative = insights_path.relative_to(self.config.research_dir).as_posix()
            lines.append(f"- [{title}](./{relative}) — `{slug}`")
        lines.append("")
        master_path.write_text("\n".join(lines), encoding="utf-8")
        return master_path

    def list_campaign_briefs(self) -> list[tuple[str, Path, str]]:
        """Return all existing campaign briefs under `Research/`."""
        campaigns: list[tuple[str, Path, str]] = []
        if not self.config.research_dir.exists():
            return campaigns
        for campaign_dir in sorted(self.config.research_dir.iterdir()):
            if not campaign_dir.is_dir():
                continue
            slug = campaign_dir.name
            insights_path = campaign_dir / f"{slug}_Insights.MD"
            if not insights_path.exists():
                continue
            title = self._read_title(insights_path) or slug
            campaigns.append((slug, insights_path, title))
        return campaigns

    def _read_title(self, path: Path) -> str | None:
        """Return the first Markdown H1 title from a brief, if present."""
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("# "):
                    return line.lstrip("# ").strip()
        except OSError:
            pass
        return None
