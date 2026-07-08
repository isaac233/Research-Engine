"""Unit tests for handoff docs."""

from __future__ import annotations

from pathlib import Path

from research_engine.planning.handoff import HandoffDoc


def test_handoff_writes_and_renders(tmp_path: Path) -> None:
    doc = HandoffDoc(
        campaign_id="c1",
        from_stage="extract",
        to_stage="evaluate",
        from_model="llm:gemma4:12b",
        to_model="synth_a",
        goal="find replication-grade insights",
        produced="3 sources extracted",
        open_questions="",
        next_task="synthesize",
    )
    path = doc.write(tmp_path)
    assert path.exists()
    assert path.parent.name == "c1"
    text = path.read_text(encoding="utf-8")
    assert "extract -> evaluate" in text
    assert "llm:gemma4:12b" in text
    assert "synth_a" in text
    assert "(none)" in text  # empty open_questions rendered
