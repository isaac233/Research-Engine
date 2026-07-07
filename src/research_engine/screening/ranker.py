"""Source ranker: apply a CriterionSet and produce a scorecard per source."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from research_engine.discovery.schema import Paper
from research_engine.llm.provider import LLMProvider, Message
from research_engine.screening.criteria import (
    BooleanCriterion,
    CriterionSet,
    CriterionType,
    LLMRubricCriterion,
    MatchMode,
    NumericCriterion,
    default_academic_criteria,
)


class LLMScorer(Protocol):
    """Callable that scores a paper against a rubric prompt and returns a float."""

    def __call__(self, paper: Paper, prompt: str) -> float:
        ...


@dataclass(frozen=True, slots=True)
class CriterionScore:
    """Outcome of applying one criterion to one source."""

    criterion_name: str
    passed: bool
    value: Any
    score: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class SourceScorecard:
    """Screening result for a single source."""

    paper: Paper
    criterion_scores: list[CriterionScore]
    total_score: float
    included: bool
    reason: str
    meta: dict[str, Any] = field(default_factory=dict)


class SourceRanker:
    """Rank sources using a CriterionSet."""

    def __init__(
        self,
        criteria: CriterionSet | None = None,
        llm_scorer: LLMScorer | None = None,
    ) -> None:
        self.criteria = criteria or default_academic_criteria()
        self.llm_scorer = llm_scorer

    def rank(self, papers: list[Paper], query: str = "") -> list[SourceScorecard]:
        """Return scorecards ordered by descending total score."""
        scorecards = [self._score(paper, query) for paper in papers]
        return sorted(scorecards, key=lambda s: s.total_score, reverse=True)

    def _score(self, paper: Paper, query: str) -> SourceScorecard:
        criterion_scores: list[CriterionScore] = []
        total_score = 0.0
        must_failed = False

        for criterion in self.criteria.criteria:
            score = self._apply(paper, criterion, query)
            criterion_scores.append(score)
            contribution = score.score if score.score is not None else (1.0 if score.passed else 0.0)
            weight = self._weight(criterion)
            total_score += contribution * weight
            if criterion.match_mode == MatchMode.MUST and not score.passed:
                must_failed = True

        included = not must_failed
        reason = "passed all must criteria" if included else "failed a must criterion"

        return SourceScorecard(
            paper=paper,
            criterion_scores=criterion_scores,
            total_score=round(total_score, 4),
            included=included,
            reason=reason,
            meta={"query": query, "criteria_set": self.criteria.name},
        )

    def _apply(
        self,
        paper: Paper,
        criterion: BooleanCriterion | NumericCriterion | LLMRubricCriterion,
        query: str,
    ) -> CriterionScore:
        if criterion.kind == CriterionType.BOOLEAN:
            assert isinstance(criterion, BooleanCriterion)
            return self._apply_boolean(paper, criterion)
        if criterion.kind == CriterionType.NUMERIC:
            assert isinstance(criterion, NumericCriterion)
            return self._apply_numeric(paper, criterion)
        assert isinstance(criterion, LLMRubricCriterion)
        return self._apply_llm_rubric(paper, criterion, query)

    def _apply_boolean(self, paper: Paper, criterion: BooleanCriterion) -> CriterionScore:
        value = self._resolve_field(paper, criterion.field)
        normalized = bool(value) if not isinstance(value, bool) else value
        passed = normalized == criterion.expected
        return CriterionScore(
            criterion_name=criterion.name,
            passed=passed,
            value=normalized,
            score=1.0 if passed else 0.0,
            reason=f"{criterion.field}={normalized}, expected {criterion.expected}",
        )

    def _apply_numeric(self, paper: Paper, criterion: NumericCriterion) -> CriterionScore:
        value = self._resolve_field(paper, criterion.field)
        if value is None or not isinstance(value, (int, float)):
            passed = False
            numeric_value = None
        else:
            numeric_value = float(value)
            passed = True
            if criterion.minimum is not None and numeric_value < criterion.minimum:
                passed = False
            if criterion.maximum is not None and numeric_value > criterion.maximum:
                passed = False
        return CriterionScore(
            criterion_name=criterion.name,
            passed=passed,
            value=numeric_value,
            score=1.0 if passed else 0.0,
            reason=self._numeric_reason(criterion, numeric_value, passed),
        )

    def _apply_llm_rubric(
        self,
        paper: Paper,
        criterion: LLMRubricCriterion,
        query: str,
    ) -> CriterionScore:
        if self.llm_scorer is None:
            return CriterionScore(
                criterion_name=criterion.name,
                passed=False,
                value=None,
                score=None,
                reason="No LLM scorer configured",
            )
        try:
            score = self.llm_scorer(paper, criterion.prompt.format(query=query))
            clamped = max(criterion.minimum_score, min(criterion.maximum_score, score))
            passed = clamped >= criterion.minimum_score
            normalized = (
                (clamped - criterion.minimum_score)
                / (criterion.maximum_score - criterion.minimum_score)
                if criterion.maximum_score != criterion.minimum_score
                else (1.0 if passed else 0.0)
            )
            return CriterionScore(
                criterion_name=criterion.name,
                passed=passed,
                value=clamped,
                score=round(normalized, 4),
                reason=f"LLM rubric score {clamped} vs minimum {criterion.minimum_score}",
            )
        except Exception as exc:  # noqa: BLE001
            return CriterionScore(
                criterion_name=criterion.name,
                passed=False,
                value=None,
                score=None,
                reason=f"LLM scoring failed: {exc}",
            )

    def _resolve_field(self, paper: Paper, field: str) -> Any:
        """Resolve a dot-path or meta key from a Paper."""
        if field.startswith("meta."):
            return paper.meta.get(field[5:])
        value = getattr(paper, field, None)
        if value is None and field == "has_full_text":
            return paper.pdf_url is not None
        return value

    def _weight(self, criterion: BooleanCriterion | NumericCriterion | LLMRubricCriterion) -> float:
        return criterion.weight

    def _numeric_reason(
        self,
        criterion: NumericCriterion,
        value: float | None,
        passed: bool,
    ) -> str:
        parts: list[str] = []
        if criterion.minimum is not None:
            parts.append(f">= {criterion.minimum}")
        if criterion.maximum is not None:
            parts.append(f"<= {criterion.maximum}")
        constraint = " and ".join(parts) or "any value"
        status = f"value {value} {'passes' if passed else 'fails'} {constraint}"
        return status


def build_llm_scorer(provider: LLMProvider, model: str | None = None) -> LLMScorer:
    """Return a scorer that prompts the provider for a numeric rubric score."""

    def scorer(paper: Paper, prompt: str) -> float:
        messages = [
            Message(
                role="system",
                content="You score academic papers on a numeric rubric. Reply with only a number.",
            ),
            Message(
                role="user",
                content=f"Paper title: {paper.title}\nAbstract: {paper.abstract[:800]}\n\n{prompt}\nScore:",
            ),
        ]
        response = provider.complete(messages, model=model, temperature=0.0, max_tokens=10)
        match = re.search(r"\d+(?:\.\d+)?", response)
        if match is None:
            raise ValueError(f"Could not parse score from response: {response!r}")
        return float(match.group(0))

    return scorer
