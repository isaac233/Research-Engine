"""Run the WARP native loop (AgentCPM-Report as the agent) on a bench task, score RACE+FACT.

Phase 1/2 of the v12 native-loop port. AgentCPM drives its own Initialize->Search->Write->
Expand loop; our SearXNG shim (:8080) + CDP fetcher are its Search tool. Requires the shim,
the kimi bridge (:11444), and Ollama up.

  TASK_ID=53 python scripts/run_warp_task.py
"""
from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for _p in (str(REPO / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11444")  # judge -> kimi bridge
os.environ.setdefault("RESEARCH_ENGINE_BENCH_FACT_CACHE", "1")  # clean FACT

from bench.fact import FactScorer, default_fetcher  # noqa: E402
from bench.judge import build_judge, load_jsonl  # noqa: E402
from bench.race import RaceScorer  # noqa: E402
from bench.runner import _load_maps  # noqa: E402
from research_engine.config import EngineConfig  # noqa: E402
from research_engine.discovery.sources.serp import SERPAdapter  # noqa: E402
from research_engine.llm.model_registry import ModelRegistry  # noqa: E402
from research_engine.synthesis.warp_agent import run_warp  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

AGENTCPM = os.environ.get("WARP_MODEL", "liyishanthu/AgentCPM-Report:latest")
SHIM = "http://localhost:8080/search?q={query}&format=json"
JUDGE_MODEL = "kimi-k2.7-code:cloud"


def main() -> None:
    task_id = int(os.environ.get("TASK_ID", "53"))
    task = next(t for t in load_jsonl(REPO / "bench" / "data" / "query.jsonl") if t["id"] == task_id)
    query = task["prompt"]

    config = EngineConfig(REPO)
    registry = ModelRegistry(config.model_registry_path)
    provider = registry.build_provider("ollama")
    # Load AgentCPM at full context up front so its Write actions aren't truncated at 4096.
    try:
        registry.build_ollama_client().warm(AGENTCPM, keep_alive="15m", options={"num_ctx": 24576})
    except Exception as e:  # noqa: BLE001
        logging.warning("warm failed (continuing at default ctx): %r", e)

    serp = SERPAdapter(endpoint=SHIM)
    _fetch = default_fetcher()

    def search_fn(keywords: list[str]) -> list[str]:
        res = serp.search(" ".join(keywords), limit=6)
        return [p.url for p in res.papers]

    def read_fn(url: str) -> str:
        text = _fetch(url) or ""
        return "" if text.startswith("scrape failed") else text

    logging.info("WARP loop on task %d (model=%s)...", task_id, AGENTCPM)
    result = run_warp(query, provider, AGENTCPM, search_fn, read_fn, max_expands=8, max_tokens=4000)
    logging.info(
        "WARP done: %d chars, %d actions, %d expands, %d sources",
        len(result.markdown), result.actions, result.expands, len(result.sources),
    )

    out_md = REPO / "bench" / "out" / f"warp_task{task_id}.md"
    out_md.write_text(result.markdown, encoding="utf-8")
    logging.info("article -> %s", out_md)

    criteria_map, reference_map = _load_maps()
    criteria = criteria_map.get(query)
    reference = reference_map.get(query, {}).get("article", "")
    if not criteria:
        logging.error("no criteria for task %d", task_id)
        return
    judge = build_judge("ollama", JUDGE_MODEL)
    race = RaceScorer(judge, judge_model=JUDGE_MODEL)
    fact = FactScorer(judge, judge_model=JUDGE_MODEL)
    try:
        r = race.score(task_id, query, result.markdown, reference, criteria)
        f = fact.score(task_id, result.markdown)
    finally:
        fact.close()
    print(json.dumps({
        "race": round(r.get("overall_score", 0.0) * 100, 2),
        "comp": round(r.get("comprehensiveness", 0.0) * 100, 2),
        "insight": round(r.get("insight", 0.0) * 100, 2),
        "if": round(r.get("instruction_following", 0.0) * 100, 2),
        "read": round(r.get("readability", 0.0) * 100, 2),
        "fact": round(f.get("citation_accuracy", 0.0) * 100, 2),
        "chars": len(result.markdown), "actions": result.actions,
        "expands": result.expands, "sources": len(result.sources),
    }, indent=2))


if __name__ == "__main__":
    main()
