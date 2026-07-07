"""CLI entry point for the Research Engine."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.unblock_probe import UnblockProbe
from research_engine.config import EngineConfig
from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.source_registry import SourceRegistry
from research_engine.events import EventBus
from research_engine.orchestrator import Orchestrator
from research_engine.state import CampaignStore, ResearchRequest


def _make_orchestrator(project_root: Path | None = None) -> Orchestrator:
    config = EngineConfig(project_root)
    config.engine_data_dir.mkdir(parents=True, exist_ok=True)
    store = CampaignStore(config.state_db_path())
    http = RawHTTPBrowser()
    browser = UnblockProbe(http)
    registry = SourceRegistry()
    discovery = DiscoveryPipeline(registry=registry)
    return Orchestrator(
        store,
        EventBus(store),
        browser=browser,
        discovery=discovery,
    )


@click.group()
@click.option("--project-root", type=click.Path(path_type=Path), default=None)
@click.pass_context
def cli(ctx: click.Context, project_root: Path | None) -> None:
    """Research Engine CLI."""
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = project_root


@cli.command()
@click.argument("query")
@click.option("--context", default="", help="Additional context for the research request.")
@click.option("--max-sources", default=50, type=int, help="Maximum sources to consider.")
@click.pass_context
def run(ctx: click.Context, query: str, context: str, max_sources: int) -> None:
    """Start a new research campaign."""
    orchestrator = _make_orchestrator(ctx.obj.get("project_root"))
    request = ResearchRequest(query=query, context=context, max_sources=max_sources)
    campaign = orchestrator.start_campaign(request)

    config = EngineConfig(ctx.obj.get("project_root"))
    campaign_dir, insights_path = config.campaign_paths(campaign.slug)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Campaign {campaign.id} ({campaign.slug}) started.")
    click.echo(f"Output directory: {campaign_dir}")

    final = orchestrator.run_campaign(campaign.id)
    click.echo(f"Campaign finished with status: {final.status.value}")
    click.echo(f"Final stage: {final.stage.value}")


@cli.command()
@click.argument("campaign_id")
@click.pass_context
def status(ctx: click.Context, campaign_id: str) -> None:
    """Show campaign status."""
    orchestrator = _make_orchestrator(ctx.obj.get("project_root"))
    campaign = orchestrator.store.get_campaign(campaign_id)
    if campaign is None:
        click.echo(f"Campaign not found: {campaign_id}", err=True)
        sys.exit(1)
    click.echo(f"id: {campaign.id}")
    click.echo(f"slug: {campaign.slug}")
    click.echo(f"stage: {campaign.stage.value}")
    click.echo(f"status: {campaign.status.value}")
    click.echo(f"query: {campaign.request.query}")


@cli.command()
@click.argument("campaign_id")
@click.pass_context
def pause(ctx: click.Context, campaign_id: str) -> None:
    """Pause a running campaign."""
    orchestrator = _make_orchestrator(ctx.obj.get("project_root"))
    campaign = orchestrator.pause_campaign(campaign_id)
    click.echo(f"Campaign {campaign_id} signal set; current status: {campaign.status.value}")


@cli.command()
@click.argument("campaign_id")
@click.pass_context
def resume(ctx: click.Context, campaign_id: str) -> None:
    """Resume a paused campaign."""
    orchestrator = _make_orchestrator(ctx.obj.get("project_root"))
    campaign = orchestrator.resume_campaign(campaign_id)
    click.echo(f"Campaign {campaign_id} resumed; status: {campaign.status.value}")


@cli.command()
@click.argument("campaign_id")
@click.pass_context
def kill(ctx: click.Context, campaign_id: str) -> None:
    """Kill a campaign."""
    orchestrator = _make_orchestrator(ctx.obj.get("project_root"))
    campaign = orchestrator.kill_campaign(campaign_id)
    click.echo(f"Campaign {campaign_id} kill signal set; status: {campaign.status.value}")


if __name__ == "__main__":
    cli()
