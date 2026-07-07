"""MCP/stdio adapter exposing Research Engine tools.

This module runs a Model Context Protocol server over standard input/output so
Claude Code and other MCP clients can invoke the engine as a tool.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from mcp.server import FastMCP

from research_engine.config import EngineConfig
from research_engine.main import _make_orchestrator
from research_engine.state import ResearchRequest

mcp = FastMCP("research-engine")

MAX_QUERY_LEN = 4000
MAX_MCP_SOURCES = 100


def _safe_project_root(project_root: str | None = None) -> Path:
    """Resolve ``project_root`` relative to the server CWD and reject escapes.

    The MCP server must not let a caller write state, cache, or research
    artifacts outside the directory the server was launched in.
    """
    cwd = Path.cwd().resolve()
    if project_root is None:
        return cwd
    candidate = (cwd / Path(project_root)).resolve()
    if not candidate.is_relative_to(cwd):
        raise ValueError(f"project_root must be inside {cwd}")
    return candidate


@mcp.tool()
async def research_engine_run(query: str, project_root: str | None = None) -> str:
    """Launch a research campaign for ``query`` and return the campaign summary."""
    if not query or not query.strip():
        return json.dumps({"error": "query must be non-empty"}, indent=2)
    if len(query) > MAX_QUERY_LEN:
        return json.dumps(
            {"error": f"query exceeds {MAX_QUERY_LEN} characters"}, indent=2
        )
    try:
        root = _safe_project_root(project_root)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, indent=2)
    orchestrator = _make_orchestrator(root)
    request = ResearchRequest(query=query, max_sources=MAX_MCP_SOURCES)
    campaign = orchestrator.start_campaign(request)
    final = orchestrator.run_campaign(campaign.id)

    config = EngineConfig(root)
    campaign_dir, insights_path = config.campaign_paths(final.slug)
    return json.dumps(
        {
            "campaign_id": final.id,
            "slug": final.slug,
            "status": final.status.value,
            "stage": final.stage.value,
            "campaign_dir": str(campaign_dir),
            "insights_path": str(insights_path),
        },
        indent=2,
    )


@mcp.tool()
async def research_engine_status(campaign_id: str, project_root: str | None = None) -> str:
    """Return the current status snapshot for ``campaign_id``."""
    try:
        root = _safe_project_root(project_root)
    except ValueError as exc:
        return json.dumps({"error": str(exc)}, indent=2)
    orchestrator = _make_orchestrator(root)
    snapshot = orchestrator.status_snapshot(campaign_id)
    if snapshot is None:
        return json.dumps(
            {"error": f"Campaign not found: {campaign_id}"},
            indent=2,
        )
    return json.dumps(snapshot, indent=2, default=str)


def main() -> None:
    """Run the MCP server over stdio."""
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
