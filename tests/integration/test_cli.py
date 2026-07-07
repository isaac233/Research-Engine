"""Integration tests for the research-engine CLI."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from research_engine.llm.validator import ModelStackValidator, ProviderValidation
from research_engine.main import cli
from research_engine.state import CampaignStore, ResearchRequest


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


def test_cli_status_shows_progress_and_eta() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        run_result = runner.invoke(cli, ["--project-root", tmp, "run", "test status query"])
        assert run_result.exit_code == 0
        campaign_id = run_result.output.split()[1]
        status_result = runner.invoke(cli, ["--project-root", tmp, "status", campaign_id])
        assert status_result.exit_code == 0
        assert "progress:" in status_result.output
        assert "remaining:" in status_result.output


class FakeValidator(ModelStackValidator):
    """Validator that returns deterministic results without network calls."""

    def __init__(self, providers: list[ProviderValidation]) -> None:
        self._providers = providers

    def validate_all(self) -> list[ProviderValidation]:
        return list(self._providers)

    def validate_small_local(self, provider_name: str = "ollama") -> ProviderValidation:
        for p in self._providers:
            if p.name == provider_name and p.ok:
                return ProviderValidation(
                    name=provider_name,
                    ok=True,
                    default_model="gemma2",
                    details={"models": ["gemma2"]},
                )
        return ProviderValidation(
            name=provider_name,
            ok=False,
            default_model="",
            error="no small model",
        )


def test_cli_report_renders_campaign_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        store = CampaignStore(Path(tmp) / "data" / "state.db")
        store.create_campaign(ResearchRequest(query="integration report query"))

        result = runner.invoke(cli, ["--project-root", tmp, "report"])

        assert result.exit_code == 0, result.output
        assert "Research Engine Campaign Report" in result.output
        assert "**Total campaigns**: 1" in result.output
        assert "integration report query" in result.output


def test_cli_report_writes_to_file() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        store = CampaignStore(Path(tmp) / "data" / "state.db")
        store.create_campaign(ResearchRequest(query="file report query"))
        output = Path(tmp) / "report.md"

        result = runner.invoke(cli, ["--project-root", tmp, "report", "--output", str(output)])

        assert result.exit_code == 0, result.output
        assert output.exists()
        assert "file report query" in output.read_text(encoding="utf-8")


def test_cli_report_refuses_to_overwrite_without_force() -> None:
    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "existing.md"
        output.write_text("keep me", encoding="utf-8")

        result = runner.invoke(cli, ["--project-root", tmp, "report", "--output", str(output)])

        assert result.exit_code == 1
        assert "use --force" in result.output


def test_cli_validate_models_passes_when_stack_healthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeValidator(
        [
            ProviderValidation(name="ollama", ok=True, default_model="gemma2"),
            ProviderValidation(name="anthropic", ok=True, default_model="claude-sonnet"),
        ]
    )
    monkeypatch.setattr(ModelStackValidator, "from_config", lambda _config=None: fake)

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        result = runner.invoke(cli, ["--project-root", tmp, "validate-models"])

    assert result.exit_code == 0, result.output
    assert "ollama: ok" in result.output
    assert "anthropic: ok" in result.output
    assert "small local model available: gemma2" in result.output


def test_cli_validate_models_fails_when_provider_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = FakeValidator(
        [
            ProviderValidation(
                name="ollama", ok=False, default_model="gemma2", error="connection refused"
            ),
        ]
    )
    monkeypatch.setattr(ModelStackValidator, "from_config", lambda _config=None: fake)

    runner = CliRunner()
    with tempfile.TemporaryDirectory() as tmp:
        result = runner.invoke(cli, ["--project-root", tmp, "validate-models"])

    assert result.exit_code == 1
    assert "ollama: FAIL" in result.output
    assert "connection refused" in result.output
