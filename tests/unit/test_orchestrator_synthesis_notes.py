"""V3: cross-source synthesis-notes env gate (default-off, opt-in via env)."""

from __future__ import annotations

import research_engine.orchestrator as orch


def test_synthesis_notes_disabled_by_default(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_SYNTHESIS_NOTES", raising=False)
    assert orch._synthesis_notes_enabled() is False


def test_synthesis_notes_enabled_via_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_SYNTHESIS_NOTES", "1")
    assert orch._synthesis_notes_enabled() is True
