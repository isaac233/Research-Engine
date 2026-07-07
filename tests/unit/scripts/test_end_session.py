"""Tests for scripts/end_session.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_spec = importlib.util.spec_from_file_location(
    "end_session",
    Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "end_session.py",
)
assert _spec is not None and _spec.loader is not None
end_session = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(end_session)


@pytest.fixture(autouse=True)
def _git_repo(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _fake_github_pr() -> Any:
    class FakeGithubPr:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def main(self, argv: list[str] | None = None) -> int:
            self.calls.append(argv or [])
            return 0

    return FakeGithubPr()


def test_dry_run_without_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout="")
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="feature\n")
        return _completed()

    monkeypatch.setattr(end_session.subprocess, "run", fake_run)

    result = end_session.main(["--message", "test commit"], project_root=tmp_path)
    assert result == 0
    assert ["git", "rev-parse", "--abbrev-ref", "HEAD"] in calls
    assert not any(c[:2] == ["git", "add"] for c in calls)


def test_refuses_to_run_on_main(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="main\n")
        return _completed()

    monkeypatch.setattr(end_session.subprocess, "run", fake_run)
    result = end_session.main(["--message", "test"], project_root=tmp_path)
    assert result == 1


def test_live_run_runs_cleanup_tests_commit_pr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M README.md\n")
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="feature\n")
        if cmd[:2] == [sys.executable, "-m"]:
            return _completed(stdout="1 passed\n")
        return _completed()

    monkeypatch.setattr(end_session.subprocess, "run", fake_run)

    fake_pr = _fake_github_pr()
    monkeypatch.setattr(end_session, "_load_github_pr", lambda: fake_pr)

    # Create state DB so cleanup succeeds
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "state.db").write_text("")

    handoff_path = tmp_path / "HANDOFF.md"
    handoff_path.write_text("# HANDOFF\n")

    result = end_session.main(
        ["--message", "feat: finish", "--branch", "finish/test", "--base", "main", "--live"],
        project_root=tmp_path,
    )

    assert result == 0
    # Commit is now staged/committed by github_pr.py, not end_session.py.
    assert not any(c[:2] == ["git", "add"] for c in calls)
    assert not any(c[:2] == ["git", "commit"] for c in calls)
    assert any(c[:3] == [sys.executable, "-m", "pytest"] for c in calls)
    assert fake_pr.calls == [
        [
            "--message",
            "feat: finish",
            "--branch",
            "finish/test",
            "--base",
            "main",
            "--body",
            "",
            "--live",
        ]
    ]
    assert "## End-of-session ritual" in handoff_path.read_text(encoding="utf-8")


def test_live_run_fails_when_cleanup_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="feature\n")
        return _completed()

    monkeypatch.setattr(end_session.subprocess, "run", fake_run)

    # No state DB so cleanup fails
    result = end_session.main(
        ["--message", "feat: finish", "--live"],
        project_root=tmp_path,
    )
    assert result == 1


def test_allow_main_bypasses_branch_guard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout="")
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="main\n")
        return _completed()

    monkeypatch.setattr(end_session.subprocess, "run", fake_run)

    result = end_session.main(
        ["--message", "test", "--allow-main"],
        project_root=tmp_path,
    )
    assert result == 0
