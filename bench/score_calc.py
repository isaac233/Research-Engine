"""RACE weighted-score aggregation (ported from DeepResearch Bench score_calculator).

Given the judge's per-criterion 0-10 scores for the target (article_1) and the
reference (article_2), aggregate to per-dimension weighted averages and totals
using the task's criterion + dimension weights, with the same fuzzy criterion
matching and average-weight fallback as upstream.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_DIMS = ("comprehensiveness", "insight", "instruction_following", "readability")


def _match_weight(criterion: str, dim_map: dict[str, float]) -> float | None:
    """Exact → case-insensitive → substring match of a criterion to its weight."""
    weight = dim_map.get(criterion)
    if weight is not None:
        return weight
    low = criterion.lower()
    for key, val in dim_map.items():
        if key.lower() == low:
            return val
    for key, val in dim_map.items():
        if low in key.lower() or key.lower() in low:
            return val
    return None


def calculate_weighted_scores(
    llm_output_json: dict[str, Any], criteria_data: dict[str, Any]
) -> dict[str, Any]:
    """Return {'target': {'dims':..,'total':..}, 'reference': {...}} weighted scores."""
    dimension_weights: dict[str, float] = criteria_data.get("dimension_weight", {})
    task_id = criteria_data.get("id", "?")
    criterions = criteria_data.get("criterions") or {}
    if not criterions:
        raise ValueError(f"ID {task_id}: missing criterions, cannot score")

    criterion_weights: dict[str, dict[str, float]] = {
        dim: {c["criterion"]: c["weight"] for c in crits}
        for dim, crits in criterions.items()
    }

    results: dict[str, Any] = {
        "target": {"dims": {}, "total": 0.0},
        "reference": {"dims": {}, "total": 0.0},
    }
    total_target = 0.0
    total_reference = 0.0

    for dim, scores_list in llm_output_json.items():
        if not isinstance(scores_list, list):
            continue
        if dim not in dimension_weights or dim not in criterion_weights:
            continue
        dim_map = criterion_weights[dim]
        if not dim_map:
            continue

        t_sum = r_sum = w_sum = 0.0
        had_reference = False
        avg_weight = sum(dim_map.values()) / len(dim_map)

        for item in scores_list:
            if not isinstance(item, dict):
                continue
            crit = item.get("criterion")
            crit = crit.strip() if isinstance(crit, str) else None
            a1 = item.get("article_1_score", item.get("target_score"))
            a2 = item.get("article_2_score")
            if crit is None or a1 is None:
                continue
            try:
                a1f = float(a1)
                a2f = float(a2) if a2 is not None else None
            except (TypeError, ValueError):
                continue
            weight = _match_weight(crit, dim_map)
            if weight is None:
                weight = avg_weight
            t_sum += a1f * weight
            w_sum += weight
            if a2f is not None:
                r_sum += a2f * weight
                had_reference = True

        t_avg = t_sum / w_sum if w_sum > 0 else 0.0
        r_avg = r_sum / w_sum if (w_sum > 0 and had_reference) else 0.0
        results["target"]["dims"][f"{dim}_weighted_avg"] = t_avg
        results["reference"]["dims"][f"{dim}_weighted_avg"] = r_avg

        dim_w = dimension_weights.get(dim, 0)
        total_target += t_avg * dim_w
        total_reference += r_avg * dim_w

    results["target"]["total"] = total_target
    results["reference"]["total"] = total_reference
    return results


def normalize_scores(scores: dict[str, Any]) -> dict[str, float]:
    """Reference-normalized RACE metric: target/(target+reference), 0.5 = ties reference."""
    t_total = scores["target"]["total"]
    r_total = scores["reference"]["total"]
    overall = t_total / (t_total + r_total) if (t_total + r_total) > 0 else 0.0
    out: dict[str, float] = {"overall_score": overall}
    for dim in _DIMS:
        key = f"{dim}_weighted_avg"
        t = scores["target"]["dims"].get(key, 0.0)
        r = scores["reference"]["dims"].get(key, 0.0)
        out[dim] = t / (t + r) if (t + r) > 0 else 0.0
    return out
