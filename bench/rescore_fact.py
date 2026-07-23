"""Re-score FACT only over an existing engine.jsonl (no engine run).

The parity harness (bench/fact.py) mirrors the official pipeline's semantics
(unknown-excluded denominator, batched per-URL judging, CDP/PDF fetcher); this
driver re-judges already-generated articles so instrument changes can be
measured without re-running retrieval.

Usage:
    python -m bench.rescore_fact --engine bench/out/engine_YYYY.bak.jsonl \
        --judge ollama --judge-model kimi-k2.7-code:cloud \
        --out bench/out/fact_rescore.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from bench.fact import FactScorer
from bench.judge import build_judge, load_jsonl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True, help="engine.jsonl with articles")
    parser.add_argument("--judge", default="ollama")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--out", type=Path, default=None, help="append per-task results here")
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    wanted = {int(t) for t in args.tasks.split(",") if t.strip()} if args.tasks else None
    judge = build_judge(args.judge, args.judge_model)
    scorer = FactScorer(judge, judge_model=args.judge_model)

    try:
        for row in load_jsonl(args.engine):
            task_id = row.get("id")
            article = row.get("article") or ""
            if not article or (wanted is not None and task_id not in wanted):
                continue
            res = scorer.score(task_id, article)
            print(json.dumps(res, ensure_ascii=False), flush=True)
            if args.out:
                with args.out.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(res, ensure_ascii=False) + "\n")
    finally:
        scorer.close()  # kill the judge fetcher's lazy Chromium


if __name__ == "__main__":
    main()
