"""Tests for scripts/github_pr.py."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from typing import Any

import pytest

_spec = importlib.util.spec_from_file_location(
    "github_pr", Path(__file__).resolve().parent.parent.parent.parent / "scripts" / "github_pr.py"
)
assert _spec is not None and _spec.loader is not None
github_pr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(github_pr)


def _completed(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def test_dry_run_without_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M README.md\n")
        if cmd[:2] == ["git", "remote"]:
            return _completed(stdout="origin\n")
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="feature\n")
        return _completed()

    monkeypatch.setattr(github_pr.subprocess, "run", fake_run)

    result = github_pr.main(["--message", "test commit", "--branch", "feature"])

    assert result == 0
    assert not any(c[:2] == ["git", "checkout"] for c in calls)
    assert not any(c[:2] == ["git", "commit"] for c in calls)


def test_live_run_creates_branch_commit_push_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(cmd)
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M README.md\n")
        if cmd[:2] == ["git", "remote"]:
            return _completed(stdout="origin\n")
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="feature\n")
        return _completed()

    monkeypatch.setattr(github_pr.subprocess, "run", fake_run)

    result = github_pr.main(
        [
            "--message",
            "feat: add feature",
            "--branch",
            "feat/test",
            "--base",
            "main",
            "--live",
        ]
    )

    assert result == 0
    assert ["git", "checkout", "-b", "feat/test"] in calls
    assert ["git", "add", "-A"] in calls
    assert ["git", "commit", "-m", "feat: add feature"] in calls
    assert ["git", "push", "-u", "origin", "feat/test"] in calls
    assert any(c[:3] == ["gh", "pr", "create"] for c in calls)


def test_refuses_live_on_base_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="main\n")
        if cmd[:2] == ["git", "remote"]:
            return _completed(stdout="origin\n")
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M README.md\n")
        return _completed()

    monkeypatch.setattr(github_pr.subprocess, "run", fake_run)

    result = github_pr.main(
        ["--message", "test", "--branch", "feature", "--base", "main", "--live"]
    )

    assert result == 1


def test_returns_error_when_no_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(cmd: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["git", "remote"]:
            return _completed(stdout="\n")
        if cmd[-2:] == ["--abbrev-ref", "HEAD"]:
            return _completed(stdout="feature\n")
        if cmd[:2] == ["git", "status"]:
            return _completed(stdout=" M README.md\n")
        return _completed()

    monkeypatch.setattr(github_pr.subprocess, "run", fake_run)

    result = github_pr.main(["--message", "test", "--branch", "feature"])

    assert result == 1
