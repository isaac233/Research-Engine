"""Judge construction + JSON extraction for the benchmark.

The judge is any ``LLMProvider`` (model-agnostic). Default is Gemini via the
gemini CLI (the user's chosen judge); ``ollama`` runs fully local for offline
validation; ``anthropic`` is available for a premium judge.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from research_engine.llm.provider import LLMProvider

# Sensible strong local defaults available in this environment.
_OLLAMA_JUDGE_DEFAULT = "mistral-small3.2:latest"
_GEMINI_JUDGE_DEFAULT = "gemini-2.5-pro"


def build_judge(kind: str = "gemini", model: str | None = None) -> LLMProvider:
    """Build the judge provider for the given kind (gemini|ollama|anthropic)."""
    kind = kind.lower()
    if kind == "gemini":
        from research_engine.llm.gemini_cli_client import GeminiCLIClient

        return GeminiCLIClient(default_model=model or _GEMINI_JUDGE_DEFAULT)
    if kind == "ollama":
        from research_engine.llm.ollama_client import OllamaClient

        return OllamaClient(
            base_url="http://localhost:11434",
            default_model=model or _OLLAMA_JUDGE_DEFAULT,
            timeout=600.0,
        )
    if kind == "anthropic":
        from research_engine.llm.anthropic_client import AnthropicClient

        return AnthropicClient(
            api_key_env="ANTHROPIC_API_KEY", default_model=model or "claude-opus-4-8"
        )
    raise ValueError(f"Unknown judge kind: {kind}")


def extract_json(text: str) -> Any:
    """Extract the first JSON object/array from a possibly fenced LLM response.

    Ported from DeepResearch Bench json_extractor: strip code fences, then take
    the outermost balanced ``{...}`` or ``[...]``.
    """
    if not text:
        raise ValueError("empty response")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # Fall back to the earliest balanced brace/bracket span (object or array,
    # whichever opens first — so an array wrapped in prose isn't mis-parsed as
    # the first inner object).
    candidates = [
        (cleaned.find(o), o, c) for o, c in (("{", "}"), ("[", "]")) if cleaned.find(o) != -1
    ]
    if candidates:
        _, opener, closer = min(candidates, key=lambda t: t[0])
        start = cleaned.find(opener)
        depth = 0
        for i in range(start, len(cleaned)):
            ch = cleaned[i]
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    return json.loads(cleaned[start : i + 1])
    raise ValueError("no JSON found in response")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a .jsonl file into a list of dicts."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
