"""Wiring tests for research_engine.main deliverable-writer model resolution."""
from __future__ import annotations

import pytest

from research_engine.config import EngineConfig
from research_engine.main import _resolve_synth_model


def test_synth_model_defaults_to_synth_a_lane() -> None:
    # Unset => the synth_a lane, which resolves to a mistral tag (byte-identical default).
    model = _resolve_synth_model(EngineConfig())
    assert "mistral" in model.lower()


def test_synth_model_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RESEARCH_ENGINE_SYNTH_MODEL", "custom-writer:tag")
    assert _resolve_synth_model(EngineConfig()) == "custom-writer:tag"
