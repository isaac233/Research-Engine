"""RACE weighted-score + normalization math."""

from __future__ import annotations

from bench.score_calc import calculate_weighted_scores, normalize_scores

CRITERIA = {
    "id": 1,
    "prompt": "p",
    "dimension_weight": {
        "comprehensiveness": 0.25,
        "insight": 0.25,
        "instruction_following": 0.25,
        "readability": 0.25,
    },
    "criterions": {
        "comprehensiveness": [
            {"criterion": "C1", "explanation": "e", "weight": 0.5},
            {"criterion": "C2", "explanation": "e", "weight": 0.5},
        ],
        "insight": [{"criterion": "I1", "explanation": "e", "weight": 1.0}],
        "instruction_following": [{"criterion": "F1", "explanation": "e", "weight": 1.0}],
        "readability": [{"criterion": "R1", "explanation": "e", "weight": 1.0}],
    },
}


def _judgment() -> dict[str, list[dict[str, object]]]:
    return {
        "comprehensiveness": [
            {"criterion": "C1", "article_1_score": 8, "article_2_score": 4},
            {"criterion": "C2", "article_1_score": 6, "article_2_score": 6},
        ],
        "insight": [{"criterion": "I1", "article_1_score": 6, "article_2_score": 6}],
        "instruction_following": [
            {"criterion": "F1", "article_1_score": 10, "article_2_score": 5}
        ],
        "readability": [{"criterion": "R1", "article_1_score": 2, "article_2_score": 8}],
    }


def test_weighted_average_per_dimension() -> None:
    scores = calculate_weighted_scores(_judgment(), CRITERIA)
    # comprehensiveness: (8*0.5 + 6*0.5) / 1.0 = 7.0 target; (4*0.5+6*0.5)=5.0 ref
    assert scores["target"]["dims"]["comprehensiveness_weighted_avg"] == 7.0
    assert scores["reference"]["dims"]["comprehensiveness_weighted_avg"] == 5.0


def test_normalized_overall_ties_at_half() -> None:
    tie = {
        "comprehensiveness": [{"criterion": "C1", "article_1_score": 5, "article_2_score": 5}],
        "insight": [{"criterion": "I1", "article_1_score": 5, "article_2_score": 5}],
        "instruction_following": [{"criterion": "F1", "article_1_score": 5, "article_2_score": 5}],
        "readability": [{"criterion": "R1", "article_1_score": 5, "article_2_score": 5}],
    }
    norm = normalize_scores(calculate_weighted_scores(tie, CRITERIA))
    assert abs(norm["overall_score"] - 0.5) < 1e-9


def test_missing_criterion_uses_average_weight_fallback() -> None:
    # A criterion name the judge invented still contributes via avg-weight fallback.
    judgment = {
        "insight": [{"criterion": "totally-different-name", "article_1_score": 9, "article_2_score": 3}],
    }
    scores = calculate_weighted_scores(judgment, CRITERIA)
    assert scores["target"]["dims"]["insight_weighted_avg"] == 9.0
