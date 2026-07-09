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


def test_llm_rubric_without_scorer_passes_unchecked() -> None:
    """Offline (no LLM) environments must not exclude everything on a MUST rubric."""
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
    assert scorecards[0].included is True
    relevance = next(s for s in scorecards[0].criterion_scores if s.criterion_name == "relevance")
    assert "unchecked" in relevance.reason


def test_llm_rubric_scorer_error_fails_must() -> None:
    """A scoring failure is a real (visible) failure, not a silent pass."""
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
        raise RuntimeError("model down")

    ranker = SourceRanker(criteria=criteria, llm_scorer=scorer)
    scorecards = ranker.rank([Paper(title="Any", source="test")])
    assert scorecards[0].included is False


def test_llm_scorer_receives_query_text() -> None:
    """The relevance rubric must show the actual research query to the LLM."""
    seen_prompts: list[str] = []

    def scorer(paper: Paper, prompt: str) -> float:
        seen_prompts.append(prompt)
        return 5.0

    ranker = SourceRanker(llm_scorer=scorer)
    ranker.rank(
        [Paper(title="T", source="test", pdf_url="https://x.test/p.pdf", year=2024)],
        query="elderly demographics market size in Japan",
    )
    assert any("elderly demographics market size in Japan" in p for p in seen_prompts)


def test_default_criteria_exclude_offtopic_paper() -> None:
    """A low relevance score must exclude the paper (relevance is a MUST gate)."""

    def scorer(paper: Paper, prompt: str) -> float:
        return 1.0

    ranker = SourceRanker(llm_scorer=scorer)
    scorecards = ranker.rank(
        [Paper(title="B_s decay", source="arxiv", pdf_url="https://x.test/p.pdf", year=2024)],
        query="elderly demographics market size in Japan",
    )
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


def test_default_criteria_rank_abstractful_above_abstractless() -> None:
    """Papers with no abstract and no full text are unusable downstream;
    they must rank below papers we can actually read."""

    def scorer(paper: Paper, prompt: str) -> float:
        return 4.0  # equally relevant

    ranker = SourceRanker(llm_scorer=scorer)
    papers = [
        Paper(title="Stub", source="crossref", year=2024, doi="10.1/stub"),
        Paper(
            title="Readable",
            source="openalex",
            year=2024,
            doi="10.1/read",
            abstract="Detailed abstract with real findings.",
        ),
    ]
    scorecards = ranker.rank(papers, query="q")
    assert scorecards[0].paper.title == "Readable"
    assert scorecards[0].total_score > scorecards[1].total_score
