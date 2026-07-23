"""Integration tests for the research-engine self-eval CLI command."""

from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from research_engine.main import cli


def test_self_eval_runs_fixture_and_reports_mean_f1(tmp_path: Path) -> None:
    fixture = tmp_path / "eval_qa.json"
    fixture.write_text(
        """{
  "fixtures": [
    {
      "id": "fixture-1",
      "query": "What improves?",
      "expected_claims": ["The new method improves accuracy."],
      "sources": [
        {
          "paper": {"title": "T", "source": "test", "doi": "10.1/1"},
          "content": "We found that the new method improves accuracy.",
          "is_oa": true
        }
      ]
    }
  ]
}""",
        encoding="utf-8",
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["--project-root", str(tmp_path), "self-eval", "--fixture", str(fixture)])

    assert result.exit_code == 0, result.output
    assert "Mean F1: 1.0" in result.output
    assert "fixture-1: P=1.0 R=1.0 F1=1.0" in result.output


def test_self_eval_writes_json_report(tmp_path: Path) -> None:
    fixture = tmp_path / "eval_qa.json"
    fixture.write_text(
        """{
  "fixtures": [
    {
      "id": "fixture-1",
      "query": "What improves?",
      "expected_claims": ["The new method improves accuracy."],
      "sources": [
        {
          "paper": {"title": "T", "source": "test", "doi": "10.1/1"},
          "content": "We found that the new method improves accuracy.",
          "is_oa": true
        }
      ]
    }
  ]
}""",
        encoding="utf-8",
    )
    output = tmp_path / "report.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-root",
            str(tmp_path),
            "self-eval",
            "--fixture",
            str(fixture),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert '"mean_f1": 1.0' in output.read_text(encoding="utf-8")


def test_self_eval_fails_when_fixture_missing(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project-root", str(tmp_path), "self-eval", "--fixture", str(tmp_path / "missing.json")],
    )
    assert result.exit_code == 1
    assert "Fixture not found" in result.output or "does not exist" in result.output
