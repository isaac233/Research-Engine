"""Benchmark runner: engine reports → RACE + FACT scores → aggregate summary.

Flow: load the official tasks, run the engine over each (unless reusing a prior
engine.jsonl), then score each report with RACE (vs the vendored reference
report) and FACT (citation checks), and aggregate to headline numbers the
scorecard compares against the published leaderboard.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from bench.adapter import run_engine_task
from bench.fact import FactScorer
from bench.judge import build_judge, load_jsonl
from bench.race import RaceScorer

logger = logging.getLogger(__name__)

BENCH_DIR = Path(__file__).resolve().parent
DATA_DIR = BENCH_DIR / "data"
_DIMS = ("comprehensiveness", "insight", "instruction_following", "readability")

# Hosts that republish DeepResearch Bench's own tasks/reference reports.
# Searching a task's verbatim prompt surfaces these pages, which leak the
# benchmark's reference answers into discovery — exclude them from web search.
LEAKAGE_BLOCKLIST = "deepresearch-bench,zhipuai-infra.cn,huggingface.co/datasets"


def _load_maps() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (criteria_by_prompt, reference_article_by_prompt)."""
    criteria = {c["prompt"]: c for c in load_jsonl(DATA_DIR / "criteria.jsonl")}
    reference = {r["prompt"]: r for r in load_jsonl(DATA_DIR / "reference.jsonl")}
    return criteria, reference


def _load_tasks(limit: int | None, language: str | None) -> list[dict[str, Any]]:
    tasks = load_jsonl(DATA_DIR / "query.jsonl")
    if language:
        tasks = [t for t in tasks if t.get("language") == language]
    if limit:
        tasks = tasks[:limit]
    return tasks


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def run_benchmark(
    limit: int | None = 10,
    language: str | None = "en",
    judge_kind: str = "gemini",
    judge_model: str | None = None,
    project_root: Path | None = None,
    out_dir: Path | None = None,
    reuse_engine: bool = False,
    quality: float | None = None,
    sources: int | None = None,
) -> dict[str, Any]:
    """Run the full benchmark; return an aggregate summary dict."""
    out_dir = out_dir or (BENCH_DIR / "out")
    out_dir.mkdir(parents=True, exist_ok=True)
    engine_path = out_dir / "engine.jsonl"
    scores_path = out_dir / "scores.jsonl"

    tasks = _load_tasks(limit, language)

    # Leakage guard: keep the benchmark's own dataset pages out of discovery.
    os.environ.setdefault("RESEARCH_ENGINE_SERP_BLOCKLIST", LEAKAGE_BLOCKLIST)

    # 1) Engine reports (resumable).
    done_ids = {a["id"] for a in load_jsonl(engine_path)} if engine_path.exists() else set()
    articles: dict[Any, dict[str, Any]] = (
        {a["id"]: a for a in load_jsonl(engine_path)} if engine_path.exists() else {}
    )
    if not reuse_engine:
        for task in tasks:
            if task["id"] in done_ids:
                continue
            logger.info("Engine running task %s: %s", task["id"], task["prompt"][:70])
            result = run_engine_task(
                task, project_root=project_root, quality=quality, sources=sources
            )
            articles[task["id"]] = result
            with engine_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(result, ensure_ascii=False) + "\n")

    # 2) Score with RACE + FACT.
    criteria_map, reference_map = _load_maps()
    judge = build_judge(judge_kind, judge_model)
    race = RaceScorer(judge, judge_model=judge_model)
    fact = FactScorer(judge, judge_model=judge_model)

    per_task: list[dict[str, Any]] = []
    if scores_path.exists():
        scores_path.unlink()
    try:
        for task in tasks:
            art = articles.get(task["id"])
            if not art or not art.get("article"):
                per_task.append({"id": task["id"], "error": "no engine article"})
                continue
            prompt = task["prompt"]
            criteria = criteria_map.get(prompt)
            reference = reference_map.get(prompt, {}).get("article", "")
            if not criteria:
                per_task.append({"id": task["id"], "error": "no criteria for task"})
                continue
            race_res = race.score(task["id"], prompt, art["article"], reference, criteria)
            fact_res = fact.score(task["id"], art["article"])
            row = {"id": task["id"], "race": race_res, "fact": fact_res}
            per_task.append(row)
            with scores_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    finally:
        fact.close()  # kill the judge fetcher's lazy Chromium; don't leak one per run

    return _aggregate(per_task, judge_kind, judge_model, language, len(tasks))


def _aggregate(
    per_task: list[dict[str, Any]],
    judge_kind: str,
    judge_model: str | None,
    language: str | None,
    n_tasks: int,
) -> dict[str, Any]:
    """Reduce per-task RACE/FACT rows to headline means."""
    race_ok = [r for r in per_task if "race" in r and "error" not in r["race"]]
    fact_ok = [r for r in per_task if "fact" in r]
    summary: dict[str, Any] = {
        "judge": f"{judge_kind}:{judge_model or 'default'}",
        "language": language,
        "n_tasks": n_tasks,
        "n_scored": len(race_ok),
        "race_overall": _mean([r["race"]["overall_score"] * 100 for r in race_ok]),
        "fact_citation_accuracy": _mean(
            [r["fact"]["citation_accuracy"] * 100 for r in fact_ok]
        ),
        "fact_effective_citations": _mean(
            [float(r["fact"]["effective_citations"]) for r in fact_ok]
        ),
        "per_task": per_task,
    }
    for dim in _DIMS:
        summary[dim] = _mean([r["race"][dim] * 100 for r in race_ok])
    return summary
