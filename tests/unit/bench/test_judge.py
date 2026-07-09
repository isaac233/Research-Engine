"""JSON extraction + judge builder."""

from __future__ import annotations

import pytest

from bench.judge import build_judge, extract_json


def test_extract_bare_object() -> None:
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_fenced_json() -> None:
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_array_with_prose() -> None:
    text = 'Here is the list:\n[{"fact": "x", "url": "http://e"}]\nDone.'
    assert extract_json(text) == [{"fact": "x", "url": "http://e"}]


def test_extract_raises_without_json() -> None:
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_build_judge_unknown_kind() -> None:
    with pytest.raises(ValueError):
        build_judge("nope")


def test_build_judge_ollama_is_provider() -> None:
    judge = build_judge("ollama", model="mistral-small3.2:latest")
    assert judge.name == "ollama"
    assert judge.default_model == "mistral-small3.2:latest"
