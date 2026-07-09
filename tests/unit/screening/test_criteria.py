"""Unit tests for screening criteria schema."""

from __future__ import annotations

from research_engine.screening.criteria import (
    BooleanCriterion,
    CriterionSet,
    LLMRubricCriterion,
    MatchMode,
    NumericCriterion,
    criterion_from_dict,
    default_academic_criteria,
)


def test_boolean_criterion_round_trip() -> None:
    criterion = BooleanCriterion(
        name="has_full_text",
        field="has_full_text",
        expected=True,
        match_mode=MatchMode.MUST,
        weight=1.0,
        rationale="Only include papers we can resolve to full text",
    )
    data = criterion.to_dict()
    restored = criterion_from_dict(data)
    assert isinstance(restored, BooleanCriterion)
    assert restored.name == "has_full_text"
    assert restored.expected is True
    assert restored.match_mode == MatchMode.MUST


def test_numeric_criterion_round_trip() -> None:
    criterion = NumericCriterion(
        name="recent",
        field="year",
        minimum=2020,
        match_mode=MatchMode.SHOULD,
        weight=0.5,
    )
    data = criterion.to_dict()
    restored = criterion_from_dict(data)
    assert isinstance(restored, NumericCriterion)
    assert restored.minimum == 2020
    assert restored.match_mode == MatchMode.SHOULD


def test_llm_rubric_criterion_round_trip() -> None:
    criterion = LLMRubricCriterion(
        name="relevance",
        prompt="Rate relevance 1-5.",
        minimum_score=3.0,
        maximum_score=5.0,
        match_mode=MatchMode.MUST,
    )
    data = criterion.to_dict()
    restored = criterion_from_dict(data)
    assert isinstance(restored, LLMRubricCriterion)
    assert restored.minimum_score == 3.0
    assert restored.maximum_score == 5.0


def test_criterion_set_round_trip() -> None:
    criteria = CriterionSet(
        name="test",
        criteria=[
            BooleanCriterion(name="b", field="f", expected=True),
            NumericCriterion(name="n", field="y", minimum=2020),
        ],
    )
    data = criteria.to_dict()
    restored = CriterionSet.from_dict(data)
    assert restored.name == "test"
    assert len(restored.criteria) == 2
    assert isinstance(restored.criteria[0], BooleanCriterion)
    assert isinstance(restored.criteria[1], NumericCriterion)


def test_default_academic_criteria_members() -> None:
    criteria = default_academic_criteria()
    assert criteria.name == "default_academic"
    names = {c.name for c in criteria.criteria}
    assert names == {"has_full_text", "has_abstract", "recent_enough", "relevance"}

def test_default_full_text_is_preference_not_gate() -> None:
    """Abstract-only papers (common on crossref/openalex) must remain includable;
    relevance is the gate, full text is a ranking preference."""
    criteria = default_academic_criteria()
    full_text = next(c for c in criteria.criteria if c.name == "has_full_text")
    relevance = next(c for c in criteria.criteria if c.name == "relevance")
    assert full_text.match_mode == MatchMode.SHOULD
    assert relevance.match_mode == MatchMode.MUST
