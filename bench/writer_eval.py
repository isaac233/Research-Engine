"""Fixed-evidence writer evaluation — a CLEAN signal for writer iteration.

The N=3 benchmark is dominated by discovery/screening/fetch variance (0-4 sources
per task run-to-run), which drowns out writer changes. This harness removes that
noise: it runs discovery+extraction ONCE per task and caches the extracted sources
(which now carry ``meta.page_text``), then rebuilds the Evidence Bank deterministically
(no re-fetch) and runs ANY writer variant over the SAME evidence, scoring RACE+FACT.
So a writer A/B reflects the writer alone, and you can iterate in minutes instead of
re-running campaigns.

Usage:
  python -m bench.writer_eval collect --tasks 10        # run campaigns once, cache sources
  python -m bench.writer_eval score --variant section   # score one writer over the cache
  python -m bench.writer_eval score --all               # score every variant, compare
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from bench.fact import FactScorer
from bench.judge import build_judge
from bench.race import RaceScorer
from bench.runner import _aggregate, _load_maps, _load_tasks
from research_engine.config import EngineConfig
from research_engine.llm.provider import LLMProvider
from research_engine.main import _lane_model, _make_orchestrator, _try_provider
from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.planning.constraint_triangle import ConstraintInputs, solve
from research_engine.planning.outline_builder import OutlineBuilder
from research_engine.state import ResearchRequest
from research_engine.synthesis.attribute_writer import AttributeFirstWriter
from research_engine.synthesis.deepen import deepen_report
from research_engine.synthesis.section_writer import SectionWriter

logger = logging.getLogger(__name__)
_CACHE = Path(__file__).resolve().parent / "out" / "fixed_evidence.jsonl"

# A writer variant: (bank, query, provider, model) -> article string.
WriterFn = Callable[[EvidenceBank, str, LLMProvider, str | None], str]


def _flat(bank: EvidenceBank, query: str, provider: LLMProvider, model: str | None) -> str:
    return str(AttributeFirstWriter(provider, model).write(bank, query))


def _section(bank: EvidenceBank, query: str, provider: LLMProvider, model: str | None) -> str:
    outline = OutlineBuilder(provider, model).build(bank, query)
    return str(SectionWriter(provider, model).write(outline, bank, query))


def _section_faithful(
    bank: EvidenceBank, query: str, provider: LLMProvider, model: str | None
) -> str:
    # Section structure (RACE) + near-verbatim per-span sentences (FACT). Hypothesis:
    # best of both — outline lifts RACE, quote-tight keeps citations verifiable.
    outline = OutlineBuilder(provider, model).build(bank, query)
    return str(SectionWriter(provider, model, quote_tight=True).write(outline, bank, query))


def _section_coherent(
    bank: EvidenceBank, query: str, provider: LLMProvider, model: str | None
) -> str:
    # Sequential writer that carries narrative context between sections (WebWeaver).
    outline = OutlineBuilder(provider, model).build(bank, query)
    return str(SectionWriter(provider, model, carry_context=True).write(outline, bank, query))


def _section_deepen(
    bank: EvidenceBank, query: str, provider: LLMProvider, model: str | None
) -> str:
    # WARP: coherent draft, then diagnose shallow sections and expand from the bank.
    outline = OutlineBuilder(provider, model).build(bank, query)
    draft = SectionWriter(provider, model, carry_context=True).write(outline, bank, query)
    return str(deepen_report(draft, bank, query, provider, model)) if draft.strip() else draft


WRITERS: dict[str, WriterFn] = {
    "flat": _flat,
    "section": _section,
    "section_faithful": _section_faithful,
    "section_coherent": _section_coherent,
    "section_deepen": _section_deepen,
}


def collect(tasks_limit: int, language: str, project_root: Path | None = None) -> None:
    """Run each task's campaign once and cache its extracted sources (resumable)."""
    tasks = _load_tasks(tasks_limit, language)
    done = {r["id"] for r in _load_cache()} if _CACHE.exists() else set()
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    for task in tasks:
        if task["id"] in done:
            continue
        logger.info("collect %s: %s", task["id"], task["prompt"][:70])
        sources = _run_campaign_capture_sources(task["prompt"], project_root)
        with _CACHE.open("a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {"id": task["id"], "prompt": task["prompt"], "sources": sources},
                    ensure_ascii=False,
                )
                + "\n"
            )
        logger.info("  cached %d sources", len(sources))


def _run_campaign_capture_sources(prompt: str, project_root: Path | None) -> list[dict[str, Any]]:
    """Run a full campaign and return its extracted-source dicts (with page_text)."""
    plan = solve(ConstraintInputs(quality=0.6, time_budget_s=None, source_volume=None))
    orch = _make_orchestrator(project_root)
    campaign = orch.start_campaign(ResearchRequest(query=prompt, max_sources=plan.source_volume))
    orch.store.update_campaign(campaign.with_meta("resolved_plan", asdict(plan)))
    final = orch.run_campaign(campaign.id)
    return list(final.meta.get("extracted_sources") or []) if final else []


def score(variants: list[str], judge_kind: str, judge_model: str | None) -> dict[str, Any]:
    """Score each writer variant over the cached evidence; return {variant: summary}."""
    records = _load_cache()
    if not records:
        raise SystemExit("no cached evidence — run `collect` first")
    config = EngineConfig()
    provider = _try_provider(config)
    if provider is None:
        raise SystemExit("no LLM provider (Ollama) reachable")
    model = _lane_model(config, "synth_a", "mistral-small3.2:latest")

    criteria_map, reference_map = _load_maps()
    judge = build_judge(judge_kind, judge_model)
    race = RaceScorer(judge, judge_model=judge_model)
    fact = FactScorer(judge, judge_model=judge_model)

    results: dict[str, Any] = {}
    for variant in variants:
        writer = WRITERS[variant]
        per_task: list[dict[str, Any]] = []
        for rec in records:
            bank = EvidenceBank.from_pages(rec["sources"], lambda _u: "", rec["prompt"])
            article = writer(bank, rec["prompt"], provider, model)
            criteria = criteria_map.get(rec["prompt"])
            if not article.strip() or not criteria:
                per_task.append({"id": rec["id"], "error": "no article/criteria"})
                continue
            reference = reference_map.get(rec["prompt"], {}).get("article", "")
            per_task.append(
                {
                    "id": rec["id"],
                    "race": race.score(rec["id"], rec["prompt"], article, reference, criteria),
                    "fact": fact.score(rec["id"], article),
                }
            )
        summary = _aggregate(per_task, judge_kind, judge_model, None, len(records))
        results[variant] = summary
        logger.info(
            "variant %-10s RACE %.2f  FACT %.1f%%  E.Cit %.2f",
            variant,
            summary["race_overall"],
            summary["fact_citation_accuracy"],
            summary["fact_effective_citations"],
        )
    return results


def _load_cache() -> list[dict[str, Any]]:
    if not _CACHE.exists():
        return []
    with _CACHE.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--tasks", type=int, default=10)
    c.add_argument("--language", default="en")
    s = sub.add_parser("score")
    s.add_argument("--variant", default="section")
    s.add_argument("--all", action="store_true")
    s.add_argument("--judge", default="ollama")
    s.add_argument("--judge-model", default="kimi-k2.7-code:cloud")
    args = parser.parse_args()

    if args.cmd == "collect":
        collect(args.tasks, args.language)
    else:
        variants = list(WRITERS) if args.all else [args.variant]
        summary = score(variants, args.judge, args.judge_model)
        print(json.dumps({v: _headline(s) for v, s in summary.items()}, indent=2))


def _headline(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "race": summary["race_overall"],
        "fact_acc": summary["fact_citation_accuracy"],
        "e_cit": summary["fact_effective_citations"],
        "n_scored": summary["n_scored"],
        "readability": summary.get("readability"),
    }


if __name__ == "__main__":
    main()
