"""RaceScorer with a scripted judge."""

from __future__ import annotations

from bench.race import RaceScorer
from research_engine.llm.provider import Message

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
        "comprehensiveness": [{"criterion": "C1", "explanation": "e", "weight": 1.0}],
        "insight": [{"criterion": "I1", "explanation": "e", "weight": 1.0}],
        "instruction_following": [{"criterion": "F1", "explanation": "e", "weight": 1.0}],
        "readability": [{"criterion": "R1", "explanation": "e", "weight": 1.0}],
    },
}

_GOOD = """{"comprehensiveness":[{"criterion":"C1","article_1_score":8,"article_2_score":4}],
"insight":[{"criterion":"I1","article_1_score":6,"article_2_score":6}],
"instruction_following":[{"criterion":"F1","article_1_score":10,"article_2_score":5}],
"readability":[{"criterion":"R1","article_1_score":2,"article_2_score":8}]}"""


class _Judge:
    default_model = "fake"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, messages: list[Message], model: str | None = None,
                 temperature: float = 0.7, max_tokens: int | None = None) -> str:
        self.calls += 1
        return self.reply

    def ping(self) -> dict[str, object]:
        return {"ok": True}


def test_race_happy_path() -> None:
    res = RaceScorer(_Judge(_GOOD)).score(1, "p", "target", "ref", CRITERIA)
    assert "error" not in res
    assert abs(res["comprehensiveness"] - 8 / 12) < 1e-9
    assert abs(res["readability"] - 2 / 10) < 1e-9
    assert 0.5 < res["overall_score"] < 0.55


def test_race_missing_dimension_errors_after_retries() -> None:
    judge = _Judge('{"comprehensiveness":[{"criterion":"C1","article_1_score":8,"article_2_score":4}]}')
    res = RaceScorer(judge, max_retries=2).score(1, "p", "t", "r", CRITERIA)
    assert "error" in res
    assert judge.calls == 2
