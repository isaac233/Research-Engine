"""Reasoning-preamble stripping for GGUFs that ignore think=false (Tongyi-DR/R1/Qwen3)."""

from __future__ import annotations

from research_engine.llm.ollama_client import _strip_reasoning


def test_strips_leaked_preamble_and_close_tag() -> None:
    leaked = "We restate the fact.\n</think>\n\nPhotosynthesis converts sunlight. [e1]"
    assert _strip_reasoning(leaked) == "Photosynthesis converts sunlight. [e1]"


def test_strips_full_think_block() -> None:
    assert _strip_reasoning("<think>reasoning here</think>The answer.") == "The answer."


def test_keeps_last_answer_when_multiple_close_tags() -> None:
    assert _strip_reasoning("a</think>b</think>final") == "final"


def test_leaves_normal_output_untouched() -> None:
    text = "Japan's elderly population grows toward 2050 [e1]."
    assert _strip_reasoning(text) == text


def test_empty() -> None:
    assert _strip_reasoning("") == ""
