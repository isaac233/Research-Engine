"""Integration tests for the research-engine CLI."""

from __future__ import annotations

import tempfile
from pathlib import Path

from click.testing import CliRunner

from research_engine.main import cli


def test_cli_run_creates_campaign_and_research_folder() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        result = runner.invoke(cli, ["--project-root", tmp, "run", "test cli query"])
        assert result.exit_code == 0
        assert "Campaign" in result.output
        assert "started" in result.output
        assert "completed" in result.output

        research_dir = Path(tmp) / "Research"
        assert research_dir.exists()
        assert any(research_dir.iterdir())


def test_cli_status_missing_campaign() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        result = runner.invoke(cli, ["--project-root", tmp, "status", "not-real"])
        assert result.exit_code == 1
        assert "not found" in result.output
