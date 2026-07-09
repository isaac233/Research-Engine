"""Screening criteria schema: boolean, numeric range, and LLM-rubric criteria."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class CriterionType(StrEnum):
    """Supported criterion kinds."""

    BOOLEAN = "boolean"
    NUMERIC = "numeric"
    LLM_RUBRIC = "llm_rubric"


class MatchMode(StrEnum):
    """How a criterion contributes to an overall include/exclude decision."""

    MUST = "must"
    SHOULD = "should"
    OPTIONAL = "optional"


@dataclass(frozen=True, slots=True)
class BooleanCriterion:
    """A yes/no check, e.g. has_full_text or is_english."""

    name: str
    field: str
    expected: bool
    match_mode: MatchMode = MatchMode.MUST
    weight: float = 1.0
    rationale: str = ""
    kind: CriterionType = field(default=CriterionType.BOOLEAN, init=False)  # type: ignore[operator]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "field": self.field,
            "expected": self.expected,
            "match_mode": self.match_mode.value,
            "weight": self.weight,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BooleanCriterion:
        return cls(
            name=data["name"],
            field=data["field"],
            expected=data["expected"],
            match_mode=MatchMode(data.get("match_mode", "must")),
            weight=float(data.get("weight", 1.0)),
            rationale=data.get("rationale", ""),
        )


@dataclass(frozen=True, slots=True)
class NumericCriterion:
    """A numeric range check, e.g. year >= 2020 or citation_count >= 10."""

    name: str
    field: str
    minimum: float | None = None
    maximum: float | None = None
    match_mode: MatchMode = MatchMode.MUST
    weight: float = 1.0
    rationale: str = ""
    kind: CriterionType = field(default=CriterionType.NUMERIC, init=False)  # type: ignore[operator]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "field": self.field,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "match_mode": self.match_mode.value,
            "weight": self.weight,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NumericCriterion:
        return cls(
            name=data["name"],
            field=data["field"],
            minimum=data.get("minimum"),
            maximum=data.get("maximum"),
            match_mode=MatchMode(data.get("match_mode", "must")),
            weight=float(data.get("weight", 1.0)),
            rationale=data.get("rationale", ""),
        )


@dataclass(frozen=True, slots=True)
class LLMRubricCriterion:
    """A scored criterion produced by a local LLM, e.g. relevance 1-5."""

    name: str
    prompt: str
    minimum_score: float = 3.0
    maximum_score: float = 5.0
    match_mode: MatchMode = MatchMode.SHOULD
    weight: float = 1.0
    rationale: str = ""
    kind: CriterionType = field(default=CriterionType.LLM_RUBRIC, init=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "name": self.name,
            "prompt": self.prompt,
            "minimum_score": self.minimum_score,
            "maximum_score": self.maximum_score,
            "match_mode": self.match_mode.value,
            "weight": self.weight,
            "rationale": self.rationale,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMRubricCriterion:
        return cls(
            name=data["name"],
            prompt=data["prompt"],
            minimum_score=float(data.get("minimum_score", 3.0)),
            maximum_score=float(data.get("maximum_score", 5.0)),
            match_mode=MatchMode(data.get("match_mode", "should")),
            weight=float(data.get("weight", 1.0)),
            rationale=data.get("rationale", ""),
        )


def criterion_from_dict(data: dict[str, Any]) -> BooleanCriterion | NumericCriterion | LLMRubricCriterion:
    """Factory dispatch based on `kind`."""
    kind = CriterionType(data.get("kind", "boolean"))
    if kind == CriterionType.NUMERIC:
        return NumericCriterion.from_dict(data)
    if kind == CriterionType.LLM_RUBRIC:
        return LLMRubricCriterion.from_dict(data)
    return BooleanCriterion.from_dict(data)


@dataclass(frozen=True, slots=True)
class CriterionSet:
    """A named collection of criteria for a screening pass."""

    name: str
    criteria: list[BooleanCriterion | NumericCriterion | LLMRubricCriterion]
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "criteria": [c.to_dict() for c in self.criteria],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CriterionSet:
        return cls(
            name=data["name"],
            version=data.get("version", "1.0"),
            criteria=[criterion_from_dict(c) for c in data.get("criteria", [])],
        )


def default_academic_criteria() -> CriterionSet:
    """A conservative default set for academic paper screening."""
    return CriterionSet(
        name="default_academic",
        criteria=[
            BooleanCriterion(
                name="has_full_text",
                field="has_full_text",
                expected=True,
                match_mode=MatchMode.SHOULD,
                weight=1.5,
                rationale=(
                    "Prefer papers with resolvable full text, but do not exclude "
                    "abstract-only records — extraction degrades gracefully"
                ),
            ),
            BooleanCriterion(
                name="has_abstract",
                field="abstract",
                expected=True,
                match_mode=MatchMode.SHOULD,
                weight=2.0,
                rationale=(
                    "Title-only records (common on Crossref) give extraction "
                    "nothing to read; rank readable papers above stubs"
                ),
            ),
            BooleanCriterion(
                name="readable",
                field="is_readable",
                expected=True,
                match_mode=MatchMode.MUST,
                rationale=(
                    "A source with neither abstract nor full text cannot be "
                    "extracted or cited — a relevant-sounding title is not evidence"
                ),
            ),
            NumericCriterion(
                name="recent_enough",
                field="year",
                minimum=2000,
                match_mode=MatchMode.SHOULD,
                weight=0.5,
                rationale="Prefer papers published after 2000",
            ),
            LLMRubricCriterion(
                name="relevance",
                prompt=(
                    "Research query: {query}\n"
                    "Rate how directly this paper addresses the research query "
                    "on a scale of 1-5 (1 = unrelated topic, 5 = directly on-topic)."
                ),
                minimum_score=3.0,
                maximum_score=5.0,
                match_mode=MatchMode.MUST,
                rationale="Off-topic sources poison the whole campaign; gate on LLM relevance",
            ),
        ],
    )
