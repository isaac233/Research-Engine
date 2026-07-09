"""RACE scorer: report quality vs a reference report across 4 weighted dimensions.

Faithful port of DeepResearch Bench RACE. The judge compares the target article
(article_1) against the fixed reference article (article_2) on each task-specific
criterion; scores are weight-aggregated and reference-normalized so 0.5 means the
target ties the reference report (the leaderboard's yardstick).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from bench.judge import extract_json
from bench.prompts import RACE_MERGED_SCORE_PROMPT
from bench.score_calc import calculate_weighted_scores, normalize_scores
from research_engine.llm.provider import LLMProvider, Message

logger = logging.getLogger(__name__)

_DIMS = ("comprehensiveness", "insight", "instruction_following", "readability")


def format_criteria_list(criteria_data: dict[str, Any]) -> str:
    """Render criteria as JSON (criterion + explanation only, no weights)."""
    out: dict[str, list[dict[str, str]]] = {}
    for dim, crits in (criteria_data.get("criterions") or {}).items():
        if not isinstance(crits, list):
            continue
        out[dim] = [
            {"criterion": c["criterion"], "explanation": c["explanation"]}
            for c in crits
            if isinstance(c, dict) and "criterion" in c and "explanation" in c
        ]
    return json.dumps(out, ensure_ascii=False, indent=2)


class RaceScorer:
    """Score one target article against its reference report and criteria."""

    def __init__(
        self, judge: LLMProvider, judge_model: str | None = None, max_retries: int = 5
    ) -> None:
        self.judge = judge
        self.judge_model = judge_model
        self.max_retries = max_retries

    def score(
        self,
        task_id: Any,
        task_prompt: str,
        target_article: str,
        reference_article: str,
        criteria_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Return {id, <4 dims>, overall_score} or {id, error}."""
        prompt = RACE_MERGED_SCORE_PROMPT.format(
            task_prompt=task_prompt,
            article_1=target_article,
            article_2=reference_article,
            criteria_list=format_criteria_list(criteria_data),
        )
        last_err = ""
        for _ in range(self.max_retries):
            try:
                raw = self.judge.complete(
                    [Message(role="user", content=prompt)],
                    model=self.judge_model,
                    temperature=0.0,
                )
                parsed = extract_json(raw)
                missing = [d for d in _DIMS if d not in parsed]
                if missing:
                    raise ValueError(f"missing dimensions: {missing}")
                scores = calculate_weighted_scores(parsed, criteria_data)
                norm = normalize_scores(scores)
                return {"id": task_id, **norm}
            except Exception as exc:  # noqa: BLE001 - judge output is untrusted, retry
                last_err = f"{type(exc).__name__}: {exc}"
                logger.warning("RACE task %s retry: %s", task_id, last_err)
        return {"id": task_id, "error": last_err or "RACE scoring failed"}
