"""Unit tests for the artifact manager."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.config import EngineConfig
from research_engine.storage.artifacts import ArtifactManager


def test_write_campaign_brief_creates_file_and_evidence_map() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = EngineConfig(Path(tmp))
        manager = ArtifactManager(config)
        path = manager.write_campaign_brief("llm_slr", "# Brief", evidence_map={"key": "value"})
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "# Brief"
        evidence_path = path.parent / "evidence_map.json"
        assert evidence_path.exists()


def test_write_master_brief_lists_campaigns() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        config = EngineConfig(Path(tmp))
        manager = ArtifactManager(config)
        brief_path = manager.write_campaign_brief("topic_a", "# Topic A", evidence_map={})
        master_path = manager.write_master_brief(manager.list_campaign_briefs())
        assert master_path.exists()
        text = master_path.read_text(encoding="utf-8")
        assert "# Research Insights" in text
        assert "Topic A" in text
        assert brief_path.name in text
