"""GeminiCLIClient argv construction, stdin, and auth-error detection (mocked subprocess)."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from research_engine.llm.gemini_cli_client import GeminiCLIClient
from research_engine.llm.provider import Message


class _Completed:
    def __init__(self, returncode: int, stdout: str, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_argv_uses_prompt_and_model() -> None:
    client = GeminiCLIClient(default_model="gemini-2.5-pro", executable="/usr/bin/gemini")
    argv = client._argv("do it", model="gemini-3")
    assert argv[0] == "/usr/bin/gemini"
    assert "-p" in argv and "do it" in argv
    assert "-m" in argv and "gemini-3" in argv


def test_windows_cmd_shim_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GeminiCLIClient(executable="C:/npm/gemini.CMD")
    argv = client._argv("hi", model=None)
    assert argv[:2] == ["cmd", "/c"]


def test_complete_pipes_stdin_and_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    def fake_run(argv: list[str], **kwargs: Any) -> _Completed:
        captured["input"] = kwargs.get("input")
        return _Completed(0, "  PONG  ")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = GeminiCLIClient(executable="/usr/bin/gemini")
    out = client.complete([Message(role="user", content="say pong")])
    assert out == "PONG"
    assert "say pong" in captured["input"]


def test_auth_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv: list[str], **kwargs: Any) -> _Completed:
        return _Completed(1, "", "Please set an Auth method ... GEMINI_API_KEY")

    monkeypatch.setattr(subprocess, "run", fake_run)
    client = GeminiCLIClient(executable="/usr/bin/gemini")
    with pytest.raises(RuntimeError, match="not authenticated"):
        client.complete([Message(role="user", content="x")])


def test_ping_reports_missing_executable() -> None:
    client = GeminiCLIClient(executable=None)
    # shutil.which may still find a real gemini; force the missing path.
    client._exe = None
    assert client.ping()["ok"] is False
