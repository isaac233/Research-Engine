"""V7: entity-wise rubric env gate (default-off, opt-in via env)."""

from __future__ import annotations

import research_engine.orchestrator as orch


def test_entity_sections_disabled_by_default(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.delenv("RESEARCH_ENGINE_ENTITY_SECTIONS", raising=False)
    assert orch._entity_sections_enabled() is False


def test_entity_sections_enabled_via_env(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("RESEARCH_ENGINE_ENTITY_SECTIONS", "1")
    assert orch._entity_sections_enabled() is True
