"""Project path resolution and engine configuration."""

from __future__ import annotations

from pathlib import Path


class EngineConfig:
    """Runtime paths for the engine when embedded in a host project."""

    def __init__(self, project_root: Path | str | None = None) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self.research_dir = self.project_root / "Research"
        self.engine_data_dir = self.project_root / "data"
        self.model_registry_path = Path(__file__).resolve().parent.parent.parent / "config" / "models.yaml"

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
