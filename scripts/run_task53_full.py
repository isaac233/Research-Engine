"""Run a single DeepResearch Bench task (id=53) end-to-end with RACE + FACT scoring.

Meant for testing the full engine pipeline against a specific task, e.g. the
vague-cohort task 53 used to validate evidence-grounded scope and related v9
levers. Reads env flags as usual (``RESEARCH_ENGINE_*``); set ``OLLAMA_HOST`` to
point at the Ollama Cloud bridge when using a cloud judge inside a MITM-proxied
Claude session.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

# repo root is two levels up from this script
REPO_ROOT = Path(__file__).resolve().parents[1]
for extra in (str(REPO_ROOT / "src"), str(REPO_ROOT)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from bench.adapter import run_engine_task
from bench.fact import FactScorer
from bench.judge import build_judge, load_jsonl
from bench.race import RaceScorer
from bench.runner import _DIMS, _load_maps

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

DATA_DIR = REPO_ROOT / "bench" / "data"
OUT_DIR = REPO_ROOT / "bench" / "out"


def _load_task(task_id: int) -> dict[str, Any]:
    tasks = load_jsonl(DATA_DIR / "query.jsonl")
    for task in tasks:
        if task["id"] == task_id:
            return task
    raise ValueError(f"task id {task_id} not found")


def main() -> int:
    task_id = int(os.environ.get("TASK_ID", "53"))
    judge_kind = os.environ.get("JUDGE_KIND", "ollama")
    judge_model = os.environ.get("JUDGE_MODEL", "kimi-k2.7-code:cloud")
    quality = os.environ.get("QUALITY")
    quality = float(quality) if quality is not None else None

    logger.info("Task %s — judge %s:%s", task_id, judge_kind, judge_model or "default")
    task = _load_task(task_id)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    engine_path = OUT_DIR / f"engine_task{task_id}_full.jsonl"
    scores_path = OUT_DIR / f"scores_task{task_id}_full.jsonl"

    logger.info("Running engine campaign...")
    article = run_engine_task(task, project_root=REPO_ROOT, quality=quality)
    logger.info("Engine returned %d chars", len(article.get("article", "")))

    with engine_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(article, ensure_ascii=False) + "\n")
    logger.info("Wrote engine result to %s", engine_path)

    logger.info("Scoring RACE + FACT...")
    criteria_map, reference_map = _load_maps()
    judge = build_judge(judge_kind, judge_model)
    race = RaceScorer(judge, judge_model=judge_model)
    fact = FactScorer(judge, judge_model=judge_model)

    prompt = task["prompt"]
    criteria = criteria_map.get(prompt)
    reference = reference_map.get(prompt, {}).get("article", "")
    if not criteria:
        logger.error("No criteria for task %s", task_id)
        return 1

    race_res = race.score(task_id, prompt, article["article"], reference, criteria)
    fact_res = fact.score(task_id, article["article"])
    row: dict[str, Any] = {"id": task_id, "race": race_res, "fact": fact_res}

    with scores_path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    logger.info("Wrote scores to %s", scores_path)

    overall = race_res.get("overall_score", 0.0) * 100
    dims = {dim: race_res.get(dim, 0.0) * 100 for dim in _DIMS}
    fact_acc = fact_res.get("citation_accuracy", 0.0) * 100

    logger.info("=" * 60)
    logger.info("TASK %s RACE overall: %.2f/100", task_id, overall)
    for dim, val in dims.items():
        logger.info("  %s: %.2f/100", dim, val)
    logger.info("TASK %s FACT citation accuracy: %.1f%%", task_id, fact_acc)
    logger.info("=" * 60)

    fact.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
