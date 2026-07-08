"""CLI entry point for the Research Engine."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import click

from research_engine.browser.raw_http import RawHTTPBrowser
from research_engine.browser.unblock_probe import UnblockProbe
from research_engine.config import EngineConfig
from research_engine.dashboard import CampaignDashboard
from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import Paper
from research_engine.discovery.source_registry import SourceRegistry
from research_engine.evaluation.harness import EvaluationHarness
from research_engine.events import EventBus
from research_engine.extraction.llm_extractor import LLMSectionExtractor
from research_engine.extraction.structured import StructuredExtractor
from research_engine.llm.lane_roster import LaneRoster
from research_engine.llm.model_registry import ModelRegistry
from research_engine.llm.provider import LLMProvider
from research_engine.llm.validator import ModelStackValidator
from research_engine.monitoring.estimator import TimeEstimator
from research_engine.monitoring.gpu_probe import GpuProbe
from research_engine.orchestrator import Orchestrator
from research_engine.screening.ranker import SourceRanker, build_llm_scorer
from research_engine.state import CampaignStore, ResearchRequest
from research_engine.storage.agent_history import AgentHistory
from research_engine.storage.cache import SourceCache
from research_engine.storage.source_memory import SourceMemory
from research_engine.synthesis.synthesizer import Synthesizer


def _lane_model(config: EngineConfig, lane: str, default: str) -> str:
    """Resolve a lane's effective model tag via the LaneRoster + pull report."""
    try:
        lanes_path = config.model_registry_path.parent / "model_lanes.yaml"
        roster = LaneRoster.from_yaml(
            lanes_path, config.engine_data_dir / "model_pull_report.json"
        )
        return roster.lane(lane).tag or default
    except Exception:  # noqa: BLE001
        return default


def _try_provider(config: EngineConfig) -> LLMProvider | None:
    """Build the Ollama provider if reachable, else None (engine runs heuristic-only)."""
    try:
        provider = ModelRegistry(config.model_registry_path).build_provider("ollama")
        return provider if provider.ping().get("ok") else None
    except Exception:  # noqa: BLE001
        return None


def _build_gpu_probe(config: EngineConfig) -> GpuProbe:
    """GpuProbe with the Ollama client for residency detail (nvidia-smi always works)."""
    try:
        client = ModelRegistry(config.model_registry_path).build_ollama_client()
        return GpuProbe(ollama_client=client)
    except Exception:  # noqa: BLE001
        return GpuProbe()


def _make_orchestrator(project_root: Path | None = None) -> Orchestrator:
    config = EngineConfig(project_root)
    config.engine_data_dir.mkdir(parents=True, exist_ok=True)
    store = CampaignStore(config.state_db_path())
    cache = SourceCache(config.cache_db_path())
    source_memory = SourceMemory(config.source_memory_db_path())
    agent_history = AgentHistory(config.agent_history_db_path())
    http = RawHTTPBrowser()
    browser = UnblockProbe(http)
    registry = SourceRegistry()
    discovery = DiscoveryPipeline(registry=registry, cache=cache)

    # One provider drives every lane (per-call model override). Absent Ollama =>
    # heuristic screening + regex extraction + deterministic brief (CI/offline).
    provider = _try_provider(config)
    if provider is not None:
        extractor = StructuredExtractor(
            llm_extractor=LLMSectionExtractor(
                provider, model=_lane_model(config, "deep", "gemma4:12b")
            )
        )
        ranker = SourceRanker(
            llm_scorer=build_llm_scorer(provider, model=_lane_model(config, "fast", "gemma4:12b"))
        )
        synthesizer: Synthesizer | None = Synthesizer(
            provider, model=_lane_model(config, "synth_a", "mistral-small3.2:latest")
        )
    else:
        extractor = StructuredExtractor()
        ranker = SourceRanker()
        synthesizer = None

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
        source_memory=source_memory,
        agent_history=agent_history,
        gpu_probe=_build_gpu_probe(config),
        synthesizer=synthesizer,
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


def _validate_output_path(output: Path, project_root: Path, force: bool) -> Path:
    """Resolve an output path and ensure it is safe to write.

    The path must live inside the project root, and existing files require
    ``--force`` to overwrite.
    """
    try:
        resolved = output.resolve()
    except OSError as exc:
        raise click.ClickException(f"Invalid output path: {exc}") from None
    if not resolved.is_relative_to(project_root.resolve()):
        raise click.ClickException(
            f"Report output must be inside project root {project_root}"
        )
    if output.exists() and not force:
        raise click.ClickException(
            f"Report already exists: {output}; use --force to overwrite"
        )
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
@click.option("--max-sources", default=50, type=click.IntRange(1, 1000), help="Hard cap on sources considered (1-1000).")
@click.option("--quality", type=click.FloatRange(0.0, 1.0), default=None, help="0.0 speed .. 1.0 max quality.")
@click.option("--time-budget", "time_budget", type=click.IntRange(1, 86400), default=None, help="Time budget in seconds (auto-optimizes quality, no slider).")
@click.option("--sources", type=click.IntRange(1, 200), default=None, help="Target number of uniquely-useful sources.")
@click.pass_context
def run(
    ctx: click.Context,
    query: str,
    context: str,
    max_sources: int,
    quality: float | None,
    time_budget: int | None,
    sources: int | None,
) -> None:
    """Start a new research campaign."""
    from dataclasses import asdict

    from research_engine.cli.slider import prompt_constraints
    from research_engine.planning.constraint_triangle import ConstraintInputs, solve

    inputs = ConstraintInputs(quality=quality, time_budget_s=time_budget, source_volume=sources)
    plan = solve(inputs)
    if plan.needs_slider:
        inputs = prompt_constraints(inputs)
        plan = solve(inputs)

    orchestrator = _make_orchestrator(ctx.obj.get("project_root"))
    request = ResearchRequest(
        query=query, context=context, max_sources=min(max_sources, plan.source_volume)
    )
    campaign = orchestrator.start_campaign(request)
    orchestrator.store.update_campaign(campaign.with_meta("resolved_plan", asdict(plan)))

    config = EngineConfig(ctx.obj.get("project_root"))
    campaign_dir, insights_path = config.campaign_paths(campaign.slug)
    campaign_dir.mkdir(parents=True, exist_ok=True)
    click.echo(f"Campaign {campaign.id} ({campaign.slug}) started.")
    click.echo(
        f"Plan: quality={plan.quality_level} ({plan.quality}), "
        f"sources={plan.source_volume}, "
        f"time_budget={plan.time_budget_s if plan.time_budget_s is not None else 'none'}s "
        f"[{plan.note}]"
    )
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
    models = snapshot.get("models") or {}
    for stage_name, tag in models.items():
        click.echo(f"model[{stage_name}]: {tag}")
    gpu = snapshot.get("gpu")
    if gpu:
        click.echo(
            f"gpu: {gpu['vram_used_mb']:.0f}/{gpu['vram_total_mb']:.0f} MiB VRAM"
        )
        for m in gpu.get("models", []):
            click.echo(
                f"  loaded {m['name']}: {m['size_vram_mb']:.0f}MB VRAM "
                f"({m['offload_pct'] * 100:.0f}% offloaded to RAM)"
            )
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
        _validate_output_path(output, config.project_root, force)
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

    lanes_path = config.model_registry_path.parent / "model_lanes.yaml"
    if lanes_path.exists():
        from research_engine.llm.lane_roster import LaneRoster

        roster = LaneRoster.from_yaml(
            lanes_path, config.engine_data_dir / "model_pull_report.json"
        )
        click.echo("\nLanes:")
        for lane in validator.validate_lanes(roster):
            mark = "ok" if lane["available"] else "FAIL"
            fb = f" (fallback from {lane['requested_tag']})" if lane["used_fallback"] else ""
            fit = "in-VRAM" if lane["fits_in_vram"] else "offload"
            click.echo(
                f"  {lane['lane']:9s} {lane['tag']:30s} {mark:4s} "
                f"[{lane['role']}, ~{lane['est_vram_gb']:g}GB {fit}]{fb}"
            )

    if not summary["all_healthy"] or not small.ok:
        sys.exit(1)


def _load_fixture(fixture_path: Path) -> dict[str, Any]:
    """Load a golden-answer evaluation fixture from JSON."""
    with fixture_path.open(encoding="utf-8") as fh:
        return cast(dict[str, Any], json.load(fh))


def _run_fixture_entry(
    entry: dict[str, Any],
    extractor: StructuredExtractor,
    harness: EvaluationHarness,
) -> dict[str, Any]:
    """Extract and score a single fixture entry against its expected claims."""
    sources: list[Any] = []
    for source_def in entry.get("sources", []):
        paper = Paper(**source_def["paper"])
        source = extractor.extract(
            paper,
            content=source_def.get("content", ""),
            is_oa=source_def.get("is_oa", True),
        )
        sources.append(source)

    expected = entry.get("expected_claims", [])
    report = harness.evaluate(
        sources,
        [],
        [],
        query=entry.get("query", ""),
        expected_claims=expected,
    )

    return {
        "id": entry.get("id"),
        "query": entry.get("query"),
        "category": entry.get("category", "utility"),
        "precision": report.precision,
        "recall": report.recall,
        "f1_score": report.f1_score,
        "coverage_score": report.coverage_score,
        "quality_score": report.quality_score,
        "total_claims": report.total_claims,
        "expected_claim_count": len(expected),
    }


def _summarize_fixture_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-fixture results into summary metrics."""
    total_f1 = sum(r["f1_score"] for r in results)
    utility_results = [r for r in results if r.get("category") == "utility"]
    trap_results = [r for r in results if r.get("category") == "trap"]
    utility_mean_f1 = (
        round(sum(r["f1_score"] for r in utility_results) / len(utility_results), 4)
        if utility_results
        else 0.0
    )
    robustness_score = (
        round(sum(1 for r in trap_results if r["f1_score"] == 0.0) / len(trap_results), 4)
        if trap_results
        else 1.0
    )
    return {
        "fixture_count": len(results),
        "mean_f1": round(total_f1 / len(results), 4) if results else 0.0,
        "utility_mean_f1": utility_mean_f1,
        "robustness_score": robustness_score,
        "fixtures": results,
    }


def _write_json_report(
    summary: dict[str, Any], output: Path, project_root: Path, force: bool
) -> None:
    """Write a self-evaluation summary to a JSON file inside the project root."""
    _validate_output_path(output, project_root, force)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    click.echo(f"Self-evaluation report written to {output}")


def _print_self_eval_summary(summary: dict[str, Any]) -> None:
    """Emit a human-readable self-evaluation summary to the console."""
    click.echo(f"Self-evaluation: {summary['fixture_count']} fixtures")
    click.echo(f"Mean F1: {summary['mean_f1']}")
    click.echo(f"Utility mean F1: {summary['utility_mean_f1']}")
    click.echo(f"Robustness score: {summary['robustness_score']}")
    for result in summary["fixtures"]:
        tag = " [trap]" if result.get("category") == "trap" else ""
        click.echo(
            f"  {result['id']}{tag}: P={result['precision']} R={result['recall']} "
            f"F1={result['f1_score']} claims={result['total_claims']}/"
            f"{result['expected_claim_count']}"
        )


@cli.command(name="self-eval")
@click.option(
    "--fixture",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to a golden-answer evaluation fixture JSON file.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Path to write a JSON report (inside project root).",
)
@click.option("--force", is_flag=True, help="Overwrite existing report file.")
@click.option(
    "--threshold",
    type=float,
    default=0.0,
    show_default=True,
    help="Exit with non-zero status if mean F1 is below this threshold.",
)
@click.pass_context
def self_eval(
    ctx: click.Context,
    fixture: Path | None,
    output: Path | None,
    force: bool,
    threshold: float,
) -> None:
    """Run deterministic golden-answer evaluation against a fixture.

    This command exercises the extractor and evaluation harness on synthetic
    sources with known expected claims, producing precision/recall/F1 metrics
    that can be tracked across releases.
    """
    config = EngineConfig(ctx.obj.get("project_root"))
    fixture_path = fixture or (
        config.project_root / "tests" / "fixtures" / "eval_qa.json"
    )
    if not fixture_path.exists():
        click.echo(f"Fixture not found: {fixture_path}", err=True)
        sys.exit(1)

    data = _load_fixture(fixture_path)
    extractor = StructuredExtractor()
    harness = EvaluationHarness()
    fixture_results = [
        _run_fixture_entry(entry, extractor, harness)
        for entry in data.get("fixtures", [])
    ]
    summary = _summarize_fixture_results(fixture_results)

    if output is not None:
        _write_json_report(summary, output, config.project_root, force)

    _print_self_eval_summary(summary)

    if summary["mean_f1"] < threshold:
        click.echo(
            f"Mean F1 {summary['mean_f1']} is below threshold {threshold}", err=True
        )
        sys.exit(1)


if __name__ == "__main__":
    cli()
