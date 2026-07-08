"""Unit tests for the model lane roster."""

from __future__ import annotations

import json
from pathlib import Path

from research_engine.llm.lane_roster import LaneRoster

_YAML = """
lanes:
  fast:
    role: reviewer
    tag: "gemma4:12b"
    fallback: "gemma4:latest"
    est_vram_gb: 8
    fits_in_vram: true
    num_ctx: 8192
    enabled: true
    use: "screening"
  deep:
    role: worker
    tag: "gemma4:26b-a4b"
    fallback: "gemma4:12b"
    est_vram_gb: 15
    fits_in_vram: false
    num_ctx: 24576
    enabled: true
    use: "extraction"
  disabled_lane:
    role: worker
    tag: "nope:1b"
    fallback: "gemma4:latest"
    enabled: false
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_from_yaml_without_report_uses_requested_tag(tmp_path: Path) -> None:
    roster = LaneRoster.from_yaml(_write(tmp_path, "lanes.yaml", _YAML))
    assert roster.lane("deep").tag == "gemma4:26b-a4b"
    assert roster.lane("deep").requested_tag == "gemma4:26b-a4b"


def test_from_yaml_honors_pull_report_fallback(tmp_path: Path) -> None:
    lanes = _write(tmp_path, "lanes.yaml", _YAML)
    report = _write(
        tmp_path,
        "report.json",
        json.dumps({"results": [{"lane": "deep", "resolved_tag": "gemma4:12b"}]}),
    )
    roster = LaneRoster.from_yaml(lanes, report)
    deep = roster.lane("deep")
    assert deep.tag == "gemma4:12b"  # resolved fallback
    assert deep.requested_tag == "gemma4:26b-a4b"  # original preserved


def test_lane_for_role_and_enabled(tmp_path: Path) -> None:
    roster = LaneRoster.from_yaml(_write(tmp_path, "lanes.yaml", _YAML))
    assert roster.lane_for_role("reviewer").name == "fast"
    names = {lane.name for lane in roster.enabled_lanes()}
    assert names == {"fast", "deep"}
    assert "disabled_lane" not in names
