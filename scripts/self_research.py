"""Run the Research Engine on its own codebase to surface improvement opportunities.

This script builds a synthetic local corpus from project docs and key source
files, then drives a full campaign through the orchestrator with discovery
monkey-patched to return that corpus. The resulting insight brief, evaluation
report, and stage timings are written to a JSON file for later comparison.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

from click.testing import CliRunner

# Allow imports from repo root regardless of cwd.
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

# ruff: noqa: E402
from research_engine.config import EngineConfig
from research_engine.discovery.pipeline import DiscoveryPipeline
from research_engine.discovery.schema import (
    DiscoveryResult,
    DuplicateGroup,
    Paper,
    ResolveResult,
    SearchResult,
)
from research_engine.evaluation.harness import EvaluationReport
from research_engine.evaluation.improvement import ImprovementProposer
from research_engine.main import cli
from research_engine.state import CampaignStore

# Pattern to extract the campaign id printed by the CLI.
_CAMPAIGN_ID_RE = re.compile(r"Campaign\s+([a-f0-9\-]+)\s+")

_DEFAULT_TARGET_FILES = [
    "README.md",
    "HANDOFF.md",
    "docs/architecture/orchestrator.md",
    "docs/architecture/evaluation.md",
    "docs/architecture/monitoring.md",
    "docs/architecture/discovery.md",
    "docs/architecture/storage.md",
    "docs/architecture/browser.md",
    "docs/plan/master_plan.md",
    "src/research_engine/evaluation/harness.py",
    "src/research_engine/evaluation/improvement.py",
    "src/research_engine/extraction/structured.py",
    "src/research_engine/main.py",
    "tests/fixtures/eval_qa.json",
]

# Directories to ignore when discovering files for the local corpus.
_SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".claude",
        "data",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
    }
)

_SELF_RESEARCH_STOPWORDS: frozenset[str] = frozenset(
    {
        "what",
        "are",
        "the",
        "for",
        "and",
        "from",
        "how",
        "does",
        "should",
        "based",
        "own",
        "its",
        "can",
        "with",
        "this",
        "that",
        "about",
        "have",
        "has",
        "had",
        "will",
        "would",
        "could",
    }
)

_SELF_RESEARCH_EXTENSIONS: frozenset[str] = frozenset(
    {".md", ".py", ".json", ".yml", ".yaml", ".toml"}
)


def _query_keywords(query: str) -> set[str]:
    """Extract meaningful lowercase keywords from the research query."""
    return {
        word
        for word in re.findall(r"[a-z0-9]+", query.lower())
        if len(word) >= 4 and word not in _SELF_RESEARCH_STOPWORDS
    }


def _discover_target_files(query: str, max_files: int = 20) -> list[Path]:
    """Dynamically select local files whose names or content match the query."""
    keywords = _query_keywords(query)
    if not keywords:
        return [repo_root / p for p in _DEFAULT_TARGET_FILES]

    scores: dict[Path, int] = {}
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in _SELF_RESEARCH_EXTENSIONS:
            continue
        if any(part in _SKIP_DIRS for part in path.relative_to(repo_root).parts):
            continue

        rel = path.relative_to(repo_root).as_posix().lower()
        score = sum(2 for kw in keywords if kw in rel)
        if score == 0:
            # Only read content if the path itself didn't already match.
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")[:2000]
            except OSError:
                continue
            score = sum(1 for kw in keywords if kw in text.lower())

        if score > 0:
            scores[path] = score

    if not scores:
        return [repo_root / p for p in _DEFAULT_TARGET_FILES]

    ranked = sorted(scores, key=lambda p: scores[p], reverse=True)
    return ranked[:max_files]


def _collect_papers(target_files: list[Path]) -> list[Paper]:
    papers: list[Paper] = []
    for path in target_files:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        # Use the first non-empty line as title, rest as abstract.
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        rel_path = path.relative_to(repo_root).as_posix()
        title = lines[0] if lines else rel_path
        abstract = "\n".join(lines[1:12]) if len(lines) > 1 else text[:1000]
        # Keep the URL fields empty so extraction uses the local abstract text
        # instead of attempting to fetch a dummy remote URL.
        papers.append(
            Paper(
                title=title[:200],
                authors=["Research Engine"],
                year=2024,
                doi=f"10.9999/{path.stem}",
                abstract=abstract[:2000],
                source="local_docs",
                source_id=f"local-{path.stem}",
            )
        )
    return papers


def _make_fake_discovery_run(papers: list[Paper]) -> Any:
    def _fake_discovery_run(_self: DiscoveryPipeline, query: str, **kwargs: object) -> DiscoveryResult:
        deduped = [DuplicateGroup(canonical=p) for p in papers]
        resolved = [
            ResolveResult(
                paper_key=p.key,
                url=p.url,
                is_oa=True,
                source="local",
                reason="local corpus",
            )
            for p in papers
        ]
        return DiscoveryResult(
            query=query,
            plan={
                "queries": [{"source": "local_docs", "query": query, "priority": 1}],
                "keywords": [],
            },
            search_results=[
                SearchResult(source="local_docs", query=query, papers=papers, total=len(papers))
            ],
            deduped_groups=deduped,
            snowball_papers=[],
            resolved=resolved,
            meta={"local_corpus": True, "paper_count": len(papers)},
        )

    return _fake_discovery_run


def _campaign_id_from_output(output: str) -> str | None:
    match = _CAMPAIGN_ID_RE.search(output)
    return match.group(1) if match else None


def _extract_report(output_dir: Path, cli_output: str) -> dict[str, Any]:
    config = EngineConfig(output_dir)
    store = CampaignStore(config.state_db_path())
    campaign_id = _campaign_id_from_output(cli_output)
    campaign = store.get_campaign(campaign_id) if campaign_id else None
    if campaign is None:
        return {"error": "Could not locate campaign in state store"}

    eval_report = campaign.meta.get("evaluation_report", {})
    proposals = campaign.meta.get("improvement_proposals", [])
    return {
        "campaign_id": campaign.id,
        "slug": campaign.slug,
        "state_db": str(config.state_db_path()),
        "coverage_score": eval_report.get("coverage_score"),
        "quality_score": eval_report.get("quality_score"),
        "total_claims": eval_report.get("total_claims"),
        "proposal_count": len(proposals),
        "proposals": proposals[:10],
    }


def _self_eval_summary(output_dir: Path) -> tuple[list[dict[str, Any]], float, float]:
    """Run the golden-answer benchmark and return proposals plus mean F1."""
    eval_report_path = output_dir / "self_eval_report.json"
    runner = CliRunner()
    fixture_path = repo_root / "tests" / "fixtures" / "eval_qa.json"
    result = runner.invoke(
        cli,
        [
            "--project-root",
            str(output_dir),
            "self-eval",
            "--fixture",
            str(fixture_path),
            "--output",
            str(eval_report_path),
            "--force",
        ],
    )
    if result.exit_code != 0 or not eval_report_path.exists():
        print(
            f"WARNING: self-eval failed (exit {result.exit_code}):\n{result.output}",
            file=sys.stderr,
        )
        return [], 0.0, 0.0

    summary = json.loads(eval_report_path.read_text(encoding="utf-8"))
    total_claims = sum(f.get("total_claims", 0) for f in summary.get("fixtures", []))
    expected_count = sum(
        f.get("expected_claim_count", 0) for f in summary.get("fixtures", [])
    )
    # Use utility_mean_f1 for improvement proposals: traps are intentionally
    # scored low to measure robustness, not to drive recall-oriented changes.
    utility_mean_f1 = summary.get("utility_mean_f1", 0.0)
    robustness_score = summary.get("robustness_score", 0.0)
    report = EvaluationReport(
        total_claims=total_claims,
        f1_score=utility_mean_f1,
        meta={"expected_claim_count": expected_count},
    )
    return ImprovementProposer().propose(report), utility_mean_f1, robustness_score


def run(query: str, output_dir: Path) -> dict[str, Any]:
    """Run a self-research campaign and return captured metrics."""
    target_files = _discover_target_files(query)
    papers = _collect_papers(target_files)
    fake_run = _make_fake_discovery_run(papers)

    runner = CliRunner()
    start = time.perf_counter()
    with patch.object(DiscoveryPipeline, "run", fake_run):
        result = runner.invoke(
            cli,
            ["--project-root", str(output_dir), "run", query],
        )
    elapsed = time.perf_counter() - start

    if result.exit_code != 0:
        raise RuntimeError(f"Self-research campaign failed:\n{result.output}")

    report = _extract_report(output_dir, result.output)
    benchmark_proposals, utility_mean_f1, robustness_score = _self_eval_summary(
        output_dir
    )
    report["benchmark_proposals"] = benchmark_proposals[:10]
    report["benchmark_proposal_count"] = len(benchmark_proposals)
    report["benchmark_utility_mean_f1"] = utility_mean_f1
    report["benchmark_robustness_score"] = robustness_score
    if benchmark_proposals:
        # The generic "add fixtures" proposal is stale once the benchmark is wired in.
        report["proposals"] = [
            p
            for p in report.get("proposals", [])
            if p.get("kind") != "R051-delta-candidate"
        ]
        report["proposal_count"] = len(report["proposals"])
    return {
        "query": query,
        "elapsed_seconds": round(elapsed, 3),
        "paper_count": len(papers),
        "cli_output": result.output,
        "report": report,
    }


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Parse self-research CLI arguments."""
    parser = argparse.ArgumentParser(description="Run the Research Engine on its own docs.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=repo_root / "data" / "self_research",
        help="Directory to use as the project root for the campaign.",
    )
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=5.0,
        help="Fail if the campaign takes longer than this many seconds.",
    )
    parser.add_argument(
        "--query",
        type=str,
        default=(
            "What are the highest-impact reliability and measurement improvements "
            "for the Research Engine codebase based on its own architecture docs?"
        ),
        help="Research question to run against the local doc corpus.",
    )
    parser.add_argument(
        "--benchmark-threshold",
        type=float,
        default=None,
        help="Exit non-zero if the self-eval mean F1 is below this threshold.",
    )
    return parser.parse_args(argv)


def _write_result_json(result: dict[str, Any], output_dir: Path) -> Path:
    """Write the self-research result dictionary to a JSON file."""
    out_path = output_dir / "self_research_result.json"
    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    return out_path


def _print_result(result: dict[str, Any], out_path: Path) -> None:
    """Emit the self-research summary and captured CLI output."""
    print(f"Self-research complete in {result['elapsed_seconds']}s")
    print(f"Corpus: {result['paper_count']} local docs")
    print(f"Result written to {out_path}")
    print("\n--- CLI output ---\n")
    print(result["cli_output"])


def _check_thresholds(
    result: dict[str, Any], max_seconds: float, benchmark_threshold: float | None
) -> int:
    """Return a non-zero exit code if runtime or benchmark thresholds are violated."""
    if result["elapsed_seconds"] > max_seconds:
        print(
            f"ERROR: elapsed {result['elapsed_seconds']}s exceeds max {max_seconds}s",
            file=sys.stderr,
        )
        return 1

    if benchmark_threshold is not None:
        utility_f1 = result["report"].get("benchmark_utility_mean_f1", 0.0)
        if utility_f1 < benchmark_threshold:
            print(
                f"ERROR: benchmark utility mean F1 {utility_f1} is below threshold {benchmark_threshold}",
                file=sys.stderr,
            )
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run self-research and report results."""
    args = _parse_args(argv)
    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    result = run(args.query, output_dir)
    out_path = _write_result_json(result, output_dir)
    _print_result(result, out_path)

    return _check_thresholds(result, args.max_seconds, args.benchmark_threshold)


if __name__ == "__main__":
    sys.exit(main())
