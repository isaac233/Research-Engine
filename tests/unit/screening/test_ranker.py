"""Unit tests for the source ranker."""

from __future__ import annotations

from research_engine.discovery.schema import Paper
from research_engine.screening.criteria import (
    BooleanCriterion,
    CriterionSet,
    LLMRubricCriterion,
    MatchMode,
    NumericCriterion,
)
from research_engine.screening.ranker import SourceRanker


def test_boolean_must_excludes_paper_without_full_text() -> None:
    criteria = CriterionSet(
        name="test",
        criteria=[
            BooleanCriterion(
                name="has_full_text",
                field="has_full_text",
                expected=True,
                match_mode=MatchMode.MUST,
            )
        ],
    )
    ranker = SourceRanker(criteria=criteria)
    papers = [
        Paper(title="With PDF", source="test", pdf_url="https://example.com/paper.pdf"),
        Paper(title="Without PDF", source="test"),
    ]
    scorecards = ranker.rank(papers)
    assert scorecards[0].included is True
    assert scorecards[1].included is False


def test_numeric_range_passes_and_fails() -> None:
    criteria = CriterionSet(
        name="test",
        criteria=[
            NumericCriterion(
                name="recent",
                field="year",
                minimum=2020,
                match_mode=MatchMode.MUST,
            )
        ],
    )
    ranker = SourceRanker(criteria=criteria)
    papers = [
        Paper(title="Old", source="test", year=2010),
        Paper(title="New", source="test", year=2024),
    ]
    scorecards = ranker.rank(papers)
    by_title = {s.paper.title: s.included for s in scorecards}
    assert by_title["Old"] is False
    assert by_title["New"] is True
    assert scorecards[0].paper.title == "New"


def test_llm_rubric_uses_scorer_and_passes() -> None:
    criteria = CriterionSet(
        name="test",
        criteria=[
            LLMRubricCriterion(
                name="relevance",
                prompt="Rate relevance",
                minimum_score=3.0,
                maximum_score=5.0,
                match_mode=MatchMode.MUST,
            )
        ],
    )

    def scorer(paper: Paper, prompt: str) -> float:
        return 4.0

    ranker = SourceRanker(criteria=criteria, llm_scorer=scorer)
    papers = [Paper(title="Relevant", source="test", abstract="This paper addresses the topic.")]
    scorecards = ranker.rank(papers)
    assert scorecards[0].included is True
    assert any(s.criterion_name == "relevance" and s.score == 0.5 for s in scorecards[0].criterion_scores)


def test_llm_rubric_without_scorer_fails() -> None:
    criteria = CriterionSet(
        name="test",
        criteria=[
            LLMRubricCriterion(
                name="relevance",
                prompt="Rate relevance",
                minimum_score=3.0,
                maximum_score=5.0,
                match_mode=MatchMode.MUST,
            )
        ],
    )
    ranker = SourceRanker(criteria=criteria)
    papers = [Paper(title="Relevant", source="test")]
    scorecards = ranker.rank(papers)
    assert scorecards[0].included is False


def test_rank_orders_by_total_score() -> None:
    criteria = CriterionSet(
        name="test",
        criteria=[
            NumericCriterion(
                name="recent",
                field="year",
                minimum=2020,
                match_mode=MatchMode.SHOULD,
                weight=1.0,
            )
        ],
    )
    ranker = SourceRanker(criteria=criteria)
    papers = [
        Paper(title="Old", source="test", year=2010),
        Paper(title="New", source="test", year=2024),
    ]
    scorecards = ranker.rank(papers)
    assert scorecards[0].paper.title == "New"
    assert scorecards[1].paper.title == "Old"
