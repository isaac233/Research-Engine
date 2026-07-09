"""Run the Research Engine over a benchmark task and return its report.

Reuses the exact orchestrator the CLI builds (``main._make_orchestrator``) so the
benchmark measures the real engine, then returns the delivered brief in the
``{id, prompt, article}`` format the RACE/FACT scorers expect.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from research_engine.config import EngineConfig
from research_engine.main import _make_orchestrator
from research_engine.planning.constraint_triangle import ConstraintInputs, solve
from research_engine.state import ResearchRequest

_DEFAULT_QUALITY = 0.6  # balanced; avoids the interactive slider in headless bench runs


def run_engine_task(
    task: dict[str, Any],
    project_root: Path | None = None,
    quality: float | None = None,
    sources: int | None = None,
    time_budget: int | None = None,
) -> dict[str, Any]:
    """Run one campaign for ``task['prompt']``; return {id, prompt, article, slug, status}."""
    if quality is None and sources is None and time_budget is None:
        quality = _DEFAULT_QUALITY
    plan = solve(
        ConstraintInputs(quality=quality, time_budget_s=time_budget, source_volume=sources)
    )

    orchestrator = _make_orchestrator(project_root)
    request = ResearchRequest(query=task["prompt"], max_sources=plan.source_volume)
    campaign = orchestrator.start_campaign(request)
    orchestrator.store.update_campaign(campaign.with_meta("resolved_plan", asdict(plan)))

    config = EngineConfig(project_root)
    campaign_dir, insights_path = config.campaign_paths(campaign.slug)
    campaign_dir.mkdir(parents=True, exist_ok=True)

    final = orchestrator.run_campaign(campaign.id)
    article = str(final.meta.get("insight_brief", "")) if final else ""
    if not article and insights_path.exists():
        article = insights_path.read_text(encoding="utf-8")

    return {
        "id": task["id"],
        "prompt": task["prompt"],
        "article": article,
        "slug": campaign.slug,
        "status": final.status.value if final else "unknown",
    }
