"""Unit tests for engine path configuration."""

from __future__ import annotations

from pathlib import Path

from research_engine.config import EngineConfig


def test_default_paths_use_cwd(tmp_path) -> None:
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
