"""Integration tests for the MCP stdio adapter."""

from __future__ import annotations

import asyncio
import json
import types
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

from research_engine import mcp_adapter


class _FakeCampaign:
    def __init__(self) -> None:
        self.id = "cmp-123"
        self.slug = "test-campaign"
        self.status = types.SimpleNamespace(value="completed")
        self.stage = types.SimpleNamespace(value="DELIVER")


class _FakeOrchestrator:
    def __init__(self, project_root: Path | None = None) -> None:
        self.project_root = project_root

    def start_campaign(self, _request: Any) -> _FakeCampaign:
        return _FakeCampaign()

    def run_campaign(self, _campaign_id: str) -> _FakeCampaign:
        return _FakeCampaign()

    def status_snapshot(self, campaign_id: str) -> dict[str, Any] | None:
        if campaign_id == "missing":
            return None
        return {
            "campaign_id": campaign_id,
            "stage": "DISCOVER",
            "status": "running",
            "progress_percent": 25,
            "eta_seconds": 120,
            "remaining_stages": ["SCREEN", "EXTRACT"],
            "alerts": [],
        }


@pytest.fixture
def fake_orchestrator(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_adapter, "_make_orchestrator", _FakeOrchestrator)


def test_research_engine_run_tool(fake_orchestrator: None) -> None:
    content, _meta = asyncio.run(
        mcp_adapter.mcp.call_tool("research_engine_run", {"query": "example research question"})
    )
    payload = json.loads(content[0].text)
    assert payload["campaign_id"] == "cmp-123"
    assert payload["slug"] == "test-campaign"
    assert payload["status"] == "completed"


def test_research_engine_status_tool(fake_orchestrator: None) -> None:
    content, _meta = asyncio.run(
        mcp_adapter.mcp.call_tool("research_engine_status", {"campaign_id": "cmp-123"})
    )
    payload = json.loads(content[0].text)
    assert payload["campaign_id"] == "cmp-123"
    assert payload["progress_percent"] == 25


def test_research_engine_status_missing_campaign(fake_orchestrator: None) -> None:
    content, _meta = asyncio.run(
        mcp_adapter.mcp.call_tool("research_engine_status", {"campaign_id": "missing"})
    )
    payload = json.loads(content[0].text)
    assert "error" in payload
