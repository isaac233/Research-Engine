"""Re-score RACE only over saved article(s) — no engine run.

Companion to ``bench.rescore_fact``: that re-judges FACT; this re-judges RACE.
Its reason to exist is the R0 falsifier — comparing two saved task-53 articles
(``bench/out/r0_article_A.md`` blind vs ``r0_article_B.md`` grounded) with a
TRUSTWORTHY judge, because the local mistral judge scored them identical to 16
decimals (a known degeneracy). The kimi cloud judge must run OUTSIDE a Claude
session (the session's MITM proxy wedges the Ollama cloud path).

Two input modes:

  # A/B article files against one task's criteria+reference (the R0 case):
  python -m bench.rescore_race --task 53 \
      --article A=bench/out/r0_article_A.md --article B=bench/out/r0_article_B.md \
      --judge ollama --judge-model kimi-k2.7-code:cloud

  # every article in an engine.jsonl (like rescore_fact):
  python -m bench.rescore_race --engine bench/out/engine.jsonl \
      --judge ollama --judge-model kimi-k2.7-code:cloud

Reuses the exact tested scoring path (bench.race.RaceScorer, bench.runner
maps/tasks), so criteria/reference/normalization match a real bench run.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from bench.judge import build_judge, load_jsonl
from bench.race import RaceScorer
from bench.runner import _load_maps, _load_tasks

logger = logging.getLogger(__name__)


def _prompt_for_task(task_id: int) -> str:
    """Look up a task's prompt by id from the official query set."""
    for task in _load_tasks(None, None):
        if str(task.get("id")) == str(task_id):
            return str(task.get("prompt") or "")
    raise SystemExit(f"task id {task_id} not found in bench/data/query.jsonl")


def _score_one(
    race: RaceScorer,
    task_id: Any,
    prompt: str,
    article: str,
    criteria_map: dict[str, dict[str, Any]],
    reference_map: dict[str, dict[str, Any]],
    *,
    tag: str = "",
) -> dict[str, Any]:
    criteria = criteria_map.get(prompt)
    if not criteria:
        return {"id": task_id, "tag": tag, "error": "no criteria for task"}
    reference = reference_map.get(prompt, {}).get("article", "")
    res = race.score(task_id, prompt, article, reference, criteria)
    if tag:
        res = {"tag": tag, **res}
    return res


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, help="engine.jsonl with {id, prompt, article} rows")
    parser.add_argument(
        "--task", type=int, help="task id for --article files (prompt/criteria/reference lookup)"
    )
    parser.add_argument(
        "--article",
        action="append",
        default=[],
        metavar="TAG=PATH",
        help="labelled article file, e.g. A=bench/out/r0_article_A.md (repeatable)",
    )
    parser.add_argument("--judge", default="ollama")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--out", type=Path, default=None, help="append per-article results here")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if not args.engine and not args.article:
        raise SystemExit("give --engine ENGINE.jsonl OR --task ID --article TAG=PATH ...")
    if args.article and args.task is None:
        raise SystemExit("--article requires --task ID (to resolve prompt/criteria/reference)")

    criteria_map, reference_map = _load_maps()
    judge = build_judge(args.judge, args.judge_model)
    race = RaceScorer(judge, judge_model=args.judge_model)

    results: list[dict[str, Any]] = []
    if args.engine:
        for row in load_jsonl(args.engine):
            article = row.get("article") or ""
            prompt = row.get("prompt") or ""
            if not article or not prompt:
                continue
            results.append(
                _score_one(race, row.get("id"), prompt, article, criteria_map, reference_map)
            )
    else:
        prompt = _prompt_for_task(args.task)
        for spec in args.article:
            tag, _, path = spec.partition("=")
            if not path:
                raise SystemExit(f"bad --article {spec!r}; expected TAG=PATH")
            article = Path(path).read_text(encoding="utf-8")
            results.append(
                _score_one(
                    race, args.task, prompt, article, criteria_map, reference_map, tag=tag.strip()
                )
            )

    for res in results:
        print(json.dumps(res, ensure_ascii=False), flush=True)
        if args.out:
            with args.out.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(res, ensure_ascii=False) + "\n")

    # R0 convenience: when exactly two tagged articles were scored, print the delta
    # that decides the falsifier (target: grounded overall > blind, IF >= 0.40).
    scored = [r for r in results if "overall_score" in r]
    if len(scored) == 2 and all(r.get("tag") for r in scored):
        a, b = scored
        d_overall = b["overall_score"] - a["overall_score"]
        d_if = b["instruction_following"] - a["instruction_following"]
        logger.info(
            "DELTA %s->%s  overall %+.4f (%.4f->%.4f)  IF %+.4f (%.4f->%.4f)",
            a["tag"], b["tag"],
            d_overall, a["overall_score"], b["overall_score"],
            d_if, a["instruction_following"], b["instruction_following"],
        )


if __name__ == "__main__":
    main()
