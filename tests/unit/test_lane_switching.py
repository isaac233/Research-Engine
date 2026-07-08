"""Orchestrator lane-switching (Phase 6 lifecycle wiring)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from research_engine.llm.lane_roster import LaneRoster
from research_engine.orchestrator import Orchestrator
from research_engine.state import CampaignStore, ResearchRequest

_LANES = """
lanes:
  deep:
    role: worker
    tag: "gemma4:12b"
    fallback: "gemma4:latest"
    num_ctx: 24576
    enabled: true
"""


class FakeLifecycle:
    def __init__(self) -> None:
        self.current: str | None = None
        self.switched: list[tuple[str, int | None]] = []
        self.unloaded: list[str] = []

    def switch(self, to_tag: str, num_ctx: int | None = None) -> bool:
        self.switched.append((to_tag, num_ctx))
        self.current = to_tag
        return True

    def unload(self, tag: str) -> bool:
        self.unloaded.append(tag)
        self.current = None
        return True


def _roster(tmp: Path) -> LaneRoster:
    p = tmp / "model_lanes.yaml"
    p.write_text(_LANES, encoding="utf-8")
    return LaneRoster.from_yaml(p)


def test_switch_lane_loads_assigned_model() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = CampaignStore(tmp_path / "state.db")
        life = FakeLifecycle()
        orch = Orchestrator(store, lifecycle=life, lane_roster=_roster(tmp_path))  # type: ignore[arg-type]
        campaign = orch.start_campaign(ResearchRequest(query="q"))
        campaign = store.update_campaign(
            campaign.with_meta("resolved_plan", {"lane_assignment": {"extract": "deep"}})
        )
        orch._switch_lane(campaign, "extract")
        assert life.switched == [("gemma4:12b", 24576)]


def test_switch_lane_noop_without_assignment() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        store = CampaignStore(tmp_path / "state.db")
        life = FakeLifecycle()
        orch = Orchestrator(store, lifecycle=life, lane_roster=_roster(tmp_path))  # type: ignore[arg-type]
        campaign = orch.start_campaign(ResearchRequest(query="q"))
        orch._switch_lane(campaign, "extract")  # no resolved_plan
        assert life.switched == []


def test_switch_lane_noop_without_lifecycle() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = CampaignStore(Path(tmp) / "state.db")
        orch = Orchestrator(store)  # no lifecycle
        campaign = orch.start_campaign(ResearchRequest(query="q"))
        orch._switch_lane(campaign, "extract")  # must not raise
