"""CLI entry point for the Research Engine."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.unblock_probe import UnblockProbe
from research_engine.config import EngineConfig
from research_engine.dashboard import CampaignDashboard
from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.source_registry import SourceRegistry
from research_engine.events import EventBus
from research_engine.extraction.structured import StructuredExtractor
from research_engine.llm.validator import ModelStackValidator
from research_engine.monitoring.estimator import TimeEstimator
from research_engine.orchestrator import Orchestrator
from research_engine.screening.ranker import SourceRanker
from research_engine.state import CampaignStore, ResearchRequest
from research_engine.storage.cache import SourceCache


def _make_orchestrator(project_root: Path | None = None) -> Orchestrator:
    config = EngineConfig(project_root)
    config.engine_data_dir.mkdir(parents=True, exist_ok=True)
    store = CampaignStore(config.state_db_path())
    cache = SourceCache(config.cache_db_path())
    http = RawHTTPBrowser()
    browser = UnblockProbe(http)
    registry = SourceRegistry()
    discovery = DiscoveryPipeline(registry=registry, cache=cache)
    ranker = SourceRanker()
    extractor = StructuredExtractor()
    event_bus = EventBus(store)
    estimator = TimeEstimator(store)
    return Orchestrator(
        store,
        event_bus,
        browser=browser,
        discovery=discovery,
        ranker=ranker,
        extractor=extractor,
        project_root=project_root,
        estimator=estimator,
    )


def _safe_cli_project_root(project_root: Path | None) -> Path | None:
    """Resolve a CLI-supplied project root and reject relative escapes.

    Absolute paths are accepted because the CLI is driven directly by the
    local user; only relative ``..`` traversal is blocked.
    """
    if project_root is None:
        return None
    resolved = project_root.resolve()
    if not resolved.is_absolute():
        cwd = Path.cwd().resolve()
        resolved = (cwd / project_root).resolve()
        if not resolved.is_relative_to(cwd):
            raise click.BadParameter(f"project-root must be inside {cwd}")
    return resolved


@click.group()
@click.option("--project-root", type=click.Path(path_type=Path), default=None)
@click.pass_context
def cli(ctx: click.Context, project_root: Path | None) -> None:
    """Research Engine CLI."""
    ctx.ensure_object(dict)
    ctx.obj["project_root"] = _safe_cli_project_root(project_root)


@cli.command()
@click.argument("query")
@click.option("--context", default="", help="Additional context for the research request.")
@click.option("--max-sources", default=50, type=click.IntRange(1, 1000), help="Maximum sources to consider (1-1000).")
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
    snapshot = orchestrator.status_snapshot(campaign_id)
    click.echo(f"id: {campaign.id}")
    click.echo(f"slug: {campaign.slug}")
    click.echo(f"stage: {snapshot['stage']}")
    click.echo(f"status: {snapshot['status']}")
    click.echo(f"progress: {snapshot['progress_percent']}%")
    eta = snapshot["eta_seconds"]
    click.echo(f"eta_seconds: {eta if eta is not None else 'unknown'}")
    click.echo(f"remaining: {', '.join(snapshot['remaining_stages'])}")
    click.echo(f"query: {campaign.request.query}")
    if snapshot["alerts"]:
        click.echo(f"alerts: {len(snapshot['alerts'])}")


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


@cli.command(name="report")
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Path to write markdown report.")
@click.option("--force", is_flag=True, help="Overwrite existing report file.")
@click.pass_context
def report(ctx: click.Context, output: Path | None, force: bool) -> None:
    """Generate an analytics report for all campaigns."""
    config = EngineConfig(ctx.obj.get("project_root"))
    if output is not None:
        try:
            resolved_output = output.resolve()
        except OSError as exc:
            click.echo(f"Invalid output path: {exc}", err=True)
            sys.exit(1)
        if not resolved_output.is_relative_to(config.project_root.resolve()):
            click.echo(
                f"Report output must be inside project root {config.project_root}", err=True
            )
            sys.exit(1)
        if output.exists() and not force:
            click.echo(f"Report already exists: {output}; use --force to overwrite", err=True)
            sys.exit(1)
    store = CampaignStore(config.state_db_path())
    dashboard = CampaignDashboard(store)
    rendered = dashboard.generate_report(output, project_root=config.project_root)
    if output is None:
        click.echo(rendered)
    else:
        click.echo(f"Report written to {output}")


@cli.command(name="validate-models")
@click.pass_context
def validate_models(ctx: click.Context) -> None:
    """Validate configured LLM providers and local model availability."""
    config = EngineConfig(ctx.obj.get("project_root"))
    validator = ModelStackValidator.from_config(config)
    results = validator.validate_all()
    summary = validator.summarize(results)
    for provider in summary["providers"]:
        status = "ok" if provider["ok"] else "FAIL"
        click.echo(f"{provider['name']}: {status} ({provider['default_model']})")
        if provider["error"]:
            click.echo(f"  error: {provider['error']}")

    small = validator.validate_small_local()
    if small.ok:
        click.echo(f"small local model available: {small.default_model}")
    else:
        click.echo(f"small local model: FAIL - {small.error}")

    if not summary["all_healthy"] or not small.ok:
        sys.exit(1)


if __name__ == "__main__":
    cli()
