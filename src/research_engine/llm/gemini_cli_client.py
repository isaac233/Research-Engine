"""Gemini judge provider that shells out to the installed ``gemini`` CLI.

Kept inside the model-agnostic ``LLMProvider`` abstraction so the benchmark's
judge can be swapped (Gemini / Ollama / Anthropic / OpenAI) by config, not code.
Bulk content is piped via stdin (the CLI appends ``-p`` to stdin) to dodge the
Windows command-line length limit, since research reports are large.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import Any

from research_engine.llm.provider import LLMProvider, Message

# A non-empty ``-p`` is required to force headless mode; it is appended AFTER the
# stdin content, so it reads as a trailing instruction.
_HEADLESS_TRIGGER = "(Follow the instructions above and output only the requested result.)"

# Substrings that mark an auth/setup failure rather than a real answer.
_AUTH_MARKERS = ("set an Auth method", "GEMINI_API_KEY", "GOOGLE_GENAI_USE", "GOOGLE_API_KEY")


class GeminiCLIClient(LLMProvider):
    """Provider backed by the ``gemini`` CLI in non-interactive (``-p``) mode."""

    name = "gemini"

    def __init__(
        self,
        default_model: str = "gemini-2.5-pro",
        timeout: float = 300.0,
        executable: str | None = None,
        max_retries: int = 3,
    ) -> None:
        self._default_model = default_model
        self.timeout = timeout
        self.max_retries = max_retries
        self._exe = executable or shutil.which("gemini")

    @property
    def default_model(self) -> str:
        return self._default_model

    def _argv(self, prompt: str, model: str | None) -> list[str]:
        if not self._exe:
            raise RuntimeError("gemini CLI not found on PATH")
        args = [self._exe, "-p", prompt, "-o", "text"]
        target = model or self._default_model
        if target:
            args += ["-m", target]
        # A .cmd/.bat shim (npm global on Windows) is not directly executable via
        # CreateProcess; route it through cmd.exe.
        if self._exe.lower().endswith((".cmd", ".bat")):
            return ["cmd", "/c", *args]
        return args

    def _run(self, stdin: str, model: str | None) -> tuple[int, str, str]:
        proc = subprocess.run(  # noqa: S603 - exe resolved via shutil.which
            self._argv(_HEADLESS_TRIGGER, model),
            input=stdin,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        format: dict[str, Any] | None = None,  # noqa: ARG002 — no CLI schema slot
        request_timeout: float | None = None,  # noqa: ARG002 — CLI-managed timeout
    ) -> str:
        # Join all messages into one stdin blob; the CLI has no separate system slot.
        stdin = "\n\n".join(
            f"{m.content}" if m.role == "user" else f"[{m.role}]\n{m.content}"
            for m in messages
        )
        last_err = ""
        for attempt in range(self.max_retries):
            try:
                code, out, err = self._run(stdin, model)
            except subprocess.TimeoutExpired:
                last_err = "gemini CLI timed out"
                continue
            text = (out or "").strip()
            blob = f"{out}\n{err}"
            if any(marker in blob for marker in _AUTH_MARKERS):
                raise RuntimeError(
                    "gemini CLI is not authenticated. Run `gemini` once to log in, "
                    "or set GEMINI_API_KEY, then retry."
                )
            if code == 0 and text:
                return text
            last_err = (err or "empty output").strip()[:300]
            time.sleep(1.5**attempt)
        raise RuntimeError(f"gemini CLI failed after {self.max_retries} tries: {last_err}")

    def ping(self) -> dict[str, Any]:
        if not self._exe:
            return {"ok": False, "error": "gemini CLI not found on PATH"}
        try:
            reply = self.complete([Message(role="user", content="Reply with the word OK.")])
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return {"ok": bool(reply), "default": self._default_model, "reply": reply[:40]}
